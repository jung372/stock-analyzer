"""
네이버 카페(주담통화/탐방) 게시글 수집을 위한 1회성 로그인 스크립트.

비밀번호는 어디에도 저장하지 않는다 — 브라우저 창을 직접 띄워 사용자가 본인 계정으로
수동 로그인(2단계 인증/캡차 포함)하면, 로그인 완료 후의 쿠키(세션)만 로컬 파일로 저장한다.

사용법:
    python naver_login_setup.py

터미널 키 입력을 기다리지 않는다 — 브라우저 창에서 로그인을 완료하면 자동으로 감지해서
다음 단계로 진행한다 (최대 대기 시간: POLL_TIMEOUT_SEC).

세션이 만료되면(브라우저에서 "네이버 세션 만료" 경고를 보게 되면) 이 스크립트를 다시 실행한다.
"""
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

_HERE = pathlib.Path(__file__).parent
SESSION_PATH = _HERE / "data" / ".naver_session.json"

LOGIN_URL = "https://nid.naver.com/nidlogin.login"
BOARD_URLS = {
    "주담통화": "https://cafe.naver.com/f-e/cafes/30608891/menus/5",
    "탐방":     "https://cafe.naver.com/f-e/cafes/30608891/menus/18",
}

POLL_INTERVAL_SEC = 2
POLL_TIMEOUT_SEC   = 480  # 8분 — 로그인/2단계 인증/캡차를 여유 있게 완료할 시간


def _is_logged_in(context) -> bool:
    """로그인 성공 여부: 네이버 로그인 후 발급되는 NID_AUT/NID_SES 쿠키 존재 여부로 판단"""
    cookie_names = {c["name"] for c in context.cookies()}
    return "NID_AUT" in cookie_names and "NID_SES" in cookie_names


def main():
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"[안내] 브라우저 창에서 네이버에 직접 로그인해주세요 ({LOGIN_URL})")
        print("[안내] 2단계 인증/캡차가 뜨면 그대로 진행하시면 됩니다.")
        print(f"[안내] 로그인 완료를 최대 {POLL_TIMEOUT_SEC}초 동안 자동으로 기다립니다...")
        page.goto(LOGIN_URL)

        waited = 0
        while waited < POLL_TIMEOUT_SEC:
            if _is_logged_in(context):
                print(f"[확인] 로그인 감지됨 ({waited}초 경과)")
                break
            time.sleep(POLL_INTERVAL_SEC)
            waited += POLL_INTERVAL_SEC
        else:
            print(f"[실패] {POLL_TIMEOUT_SEC}초 내에 로그인이 감지되지 않았습니다. 다시 실행해주세요.")
            browser.close()
            sys.exit(1)

        # 두 게시판 접근 가능 여부 확인 (로그인 페이지로 되돌아가는지만 우선 체크)
        for name, url in BOARD_URLS.items():
            page.goto(url, wait_until="networkidle")
            if "nid.naver.com" in page.url:
                print(f"[경고] '{name}' 게시판 접근 시 로그인 페이지로 리다이렉트됨 — 카페 회원 세션이 아닐 수 있습니다.")
            else:
                print(f"[확인] '{name}' 게시판 접근 확인 ({page.url})")

        context.storage_state(path=str(SESSION_PATH))
        print(f"[완료] 세션 저장됨 → {SESSION_PATH}")
        print("[완료] 이제 브라우저 창을 닫아도 됩니다.")

        browser.close()


if __name__ == "__main__":
    main()
