import json
import pathlib
from datetime import datetime, timezone

# 보고서 저장소: 종목별 JSON + _charts.html + index.json (SQLite 대체)
#   data/reports/<code>.json        — KPI + report_md + 메타 (charts_html 제외)
#   data/reports/<code>_charts.html — 차트 HTML (뷰어가 iframe src로 참조)
#   data/reports/index.json         — 생성된 종목 목록 (열람/자동완성용)
REPORTS_DIR = pathlib.Path(__file__).parent / 'reports'
INDEX_PATH  = REPORTS_DIR / 'index.json'


def init_store() -> None:
    """앱 시작 시 1회 호출 — 저장소 디렉토리/인덱스 보장"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text('[]', encoding='utf-8')


# 하위호환 별칭 (기존 호출부가 init_db를 부를 수 있음)
init_db = init_store


def _json_path(stock_code: str) -> pathlib.Path:
    return REPORTS_DIR / f'{stock_code}.json'


def _charts_path(stock_code: str) -> pathlib.Path:
    return REPORTS_DIR / f'{stock_code}_charts.html'


def get_cached_report(stock_code: str) -> dict | None:
    """캐시된 리포트 반환. 한 번이라도 생성됐으면 기간 무관 마지막 버전을 반환, 없으면 None.
    (charts_html은 형제 _charts.html 파일에서 읽어 기존 payload 형태로 합쳐 돌려준다.)"""
    path = _json_path(stock_code)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None

    charts_path = _charts_path(stock_code)
    data['charts_html'] = charts_path.read_text(encoding='utf-8') if charts_path.exists() else ''
    return data


def save_report(stock_code: str, corp_code: str, payload: dict) -> None:
    """분석 결과를 파일 저장소에 기록 (종목당 최신 1건만 유지 — 덮어쓰기)"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 차트 HTML은 별도 파일로 (JSON 경량 유지 + iframe origin 정상)
    _charts_path(stock_code).write_text(payload.get('charts_html', ''), encoding='utf-8')

    record = {
        'company_name':  payload['company_name'],
        'stock_code':    stock_code,
        'corp_code':     corp_code,
        'current_price': payload['current_price'],
        'market_cap':    payload['market_cap'],
        'shares_out':    payload['shares_out'],
        'rim_str':       payload['rim_str'],
        'report_md':     payload['report_md'],
        'generated_at':  now_iso,
    }
    _json_path(stock_code).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    _upsert_index(stock_code, payload['company_name'], now_iso)


def _upsert_index(stock_code: str, company_name: str, generated_at: str) -> None:
    """index.json에서 해당 종목 항목을 최신 정보로 교체하고 생성일 내림차순 정렬"""
    index = list_reports()
    index = [e for e in index if e.get('stock_code') != stock_code]
    index.append({
        'stock_code':   stock_code,
        'company_name': company_name,
        'generated_at': generated_at,
    })
    index.sort(key=lambda e: e.get('generated_at', ''), reverse=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')


def list_reports() -> list[dict]:
    """생성된 보고서 목록(index.json) 반환 — 뷰어 열람/자동완성용. 항상 list 반환."""
    if not INDEX_PATH.exists():
        return []
    try:
        return json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except Exception:
        return []
