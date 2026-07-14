import json
import os
import pathlib
import re
import threading
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

CLUB_ID = "30608891"
BOARDS  = {"주담통화": "5", "탐방": "18"}

MAX_POSTS_PER_STOCK  = 8     # 두 게시판 합산 최종 상한 (안전장치, broker의 MAX_FILES_PER_STOCK과 대응)
MAX_CHARS_PER_POST   = 3000  # 게시글 1건당 텍스트 상한
LOOKBACK_MONTHS      = 6     # 최근 6개월 이내 작성된 글만 대상
PAGE_SIZE            = 15
MAX_PAGES_PER_BOARD  = 20    # 안전장치: 저활동 게시판에서 6개월 경계에 못 미쳐도 무한 페이지네이션 방지
LOGIN_TIMEOUT_SEC    = 480   # 대화형 로그인 대기 시간 (8분)

SESSION_PATH = os.getenv('NAVER_CAFE_SESSION_PATH', 'data/.naver_session.json')

_LIST_URL   = "https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/{club_id}/menus/{menu_id}/articles"
_DETAIL_URL = "https://article.cafe.naver.com/gw/v4/cafes/{club_id}/articles/{article_id}"
_LOGIN_URL  = "https://nid.naver.com/nidlogin.login"

_login_lock  = threading.Lock()
_login_state = {"in_progress": False}


def _normalize(name: str) -> str:
    """종목명 정규화: 끝의 (종목코드) 괄호 제거 + 공백/대소문자 정리 (data/drive_reports.py와 동일 방식)"""
    return re.sub(r'\([^)]*\)\s*$', '', name).strip().lower()


def _is_logged_in(context) -> bool:
    """로그인 세션 유효 여부: 네이버 로그인 쿠키(NID_AUT/NID_SES) 존재 여부로 판단"""
    cookie_names = {c['name'] for c in context.cookies()}
    return 'NID_AUT' in cookie_names and 'NID_SES' in cookie_names


def has_valid_session() -> bool:
    """
    세션 파일만 가볍게 읽어 로그인 쿠키(NID_AUT/NID_SES) 존재·만료 여부를 확인 (브라우저 미실행).
    웹 UI의 로그인 상태 팝업/폴링용 — 실제 데이터 조회 가능 여부의 최종 보증은 아니다
    (그건 get_cafe_posts_for가 이미 안전하게 처리함).
    """
    path = pathlib.Path(SESSION_PATH)
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        now = datetime.now().timestamp()
        cookies = {c['name']: c for c in state.get('cookies', [])}
        for name in ('NID_AUT', 'NID_SES'):
            c = cookies.get(name)
            if not c:
                return False
            expires = c.get('expires', -1)
            if expires not in (-1, None) and expires < now:
                return False
        return True
    except Exception:
        return False


def login_in_progress() -> bool:
    return _login_state["in_progress"]


def run_login_flow(headless: bool = False, timeout_sec: int = LOGIN_TIMEOUT_SEC) -> bool:
    """
    1회성 대화형 네이버 로그인 (다른 사람이 앱을 쓸 때 웹 UI 팝업에서도, naver_login_setup.py에서도
    동일하게 재사용하는 단일 진입점).

    브라우저 창을 띄워 사용자가 직접 로그인(2단계 인증/캡차 포함)하면 쿠키(세션)만 SESSION_PATH에
    저장한다 — 비밀번호는 어디에도 남지 않는다. 동시에 하나의 로그인만 진행되도록 락으로 보호.
    """
    if not _login_lock.acquire(blocking=False):
        print('[INFO] 네이버 로그인 이미 진행 중 — 중복 요청 무시')
        return False

    _login_state["in_progress"] = True
    try:
        pathlib.Path(SESSION_PATH).parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(_LOGIN_URL)

            waited = 0
            while waited < timeout_sec:
                if _is_logged_in(context):
                    break
                time.sleep(2)
                waited += 2
            else:
                print(f'[실패] {timeout_sec}초 내에 로그인이 감지되지 않았습니다.')
                browser.close()
                return False

            for menu_id in BOARDS.values():
                page.goto(f"https://cafe.naver.com/f-e/cafes/{CLUB_ID}/menus/{menu_id}", wait_until="networkidle")

            context.storage_state(path=str(SESSION_PATH))
            browser.close()
            return True
    except Exception as e:
        print(f'[WARN] 네이버 로그인 실패: {e}')
        return False
    finally:
        _login_state["in_progress"] = False
        _login_lock.release()


def _list_recent_articles(context, menu_id: str) -> list[dict]:
    """최근 LOOKBACK_MONTHS 이내 게시글 메타데이터(제목/작성일 등)만 페이지네이션하며 수집"""
    cutoff_ms = (datetime.now() - timedelta(days=LOOKBACK_MONTHS * 30)).timestamp() * 1000

    articles = []
    for page in range(1, MAX_PAGES_PER_BOARD + 1):
        res = context.request.get(
            _LIST_URL.format(club_id=CLUB_ID, menu_id=menu_id),
            params={"page": page, "pageSize": PAGE_SIZE, "sortBy": "TIME", "viewType": "L"},
        )
        if not res.ok:
            break
        items = [
            a['item'] for a in res.json().get('result', {}).get('articleList', [])
            if a.get('type') == 'ARTICLE'
        ]
        if not items:
            break

        reached_cutoff = False
        for item in items:
            if item.get('writeDateTimestamp', 0) < cutoff_ms:
                reached_cutoff = True
                continue
            articles.append(item)

        if reached_cutoff:
            break
        time.sleep(0.3)  # 목록 페이지 간 짧은 대기

    return articles


def _fetch_article_body(context, menu_id: str, article_id: int) -> str:
    """게시글 본문 조회 → HTML 태그 제거한 순수 텍스트, MAX_CHARS_PER_POST로 절단"""
    res = context.request.get(
        _DETAIL_URL.format(club_id=CLUB_ID, article_id=article_id),
        params={"query": "", "menuId": menu_id, "boardType": "L", "useCafeId": "true", "requestFrom": "A"},
    )
    if not res.ok:
        return ""
    html = res.json().get('result', {}).get('article', {}).get('contentHtml', '')
    text = BeautifulSoup(html, 'html.parser').get_text('\n').strip()
    return text[:MAX_CHARS_PER_POST]


def get_cafe_posts_for(company_name: str, stock_code: str) -> list[dict]:
    """
    analyzer.py에서 호출하는 단일 진입점.
    세션 없음/만료/매칭 실패 → 항상 빈 리스트 반환 (전체 파이프라인을 절대 중단시키지 않음).

    두 게시판(주담통화/탐방)에서 최근 6개월 이내 글의 '제목'이 종목명 또는 종목코드와
    일치하는 경우에만 본문을 조회한다 (매칭 안 된 글은 본문을 열지 않아 요청량을 최소화).
    """
    if not pathlib.Path(SESSION_PATH).exists():
        print('[INFO] 네이버 카페 세션 없음 — naver_login_setup.py 먼저 실행 필요, 스킵')
        return []

    target_name = _normalize(company_name)
    target_code = (stock_code or '').strip()

    matched = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(SESSION_PATH))

            if not _is_logged_in(context):
                print('[WARN] 네이버 카페 세션 만료 — naver_login_setup.py 재실행 필요, 스킵')
                browser.close()
                return []

            for board_name, menu_id in BOARDS.items():
                for item in _list_recent_articles(context, menu_id):
                    subject = item.get('subject', '')
                    norm_subject = _normalize(subject)
                    if not (target_name in norm_subject or (target_code and target_code in subject)):
                        continue

                    text = _fetch_article_body(context, menu_id, item['articleId'])
                    if not text:
                        continue

                    matched.append({
                        'title':  subject,
                        'board':  board_name,
                        'date':   datetime.fromtimestamp(item['writeDateTimestamp'] / 1000).strftime('%Y-%m-%d'),
                        'author': item.get('writerInfo', {}).get('nickName', ''),
                        'url':    f"https://cafe.naver.com/f-e/cafes/{CLUB_ID}/articles/{item['articleId']}?boardtype=L&menuid={menu_id}",
                        'text':   text,
                    })

            browser.close()
    except Exception as e:
        print(f'[WARN] 네이버 카페 게시글 수집 실패, 스킵: {e}')
        return []

    matched.sort(key=lambda p: p['date'], reverse=True)
    if matched:
        print(f'[INFO] 네이버 카페 게시글 {len(matched)}건 매칭됨 (상한 {MAX_POSTS_PER_STOCK}건 적용)')
    return matched[:MAX_POSTS_PER_STOCK]
