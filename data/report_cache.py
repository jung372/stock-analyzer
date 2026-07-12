import sqlite3
import pathlib
from datetime import datetime, timezone

DB_PATH = pathlib.Path(__file__).parent / 'reports.db'

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    stock_code    TEXT PRIMARY KEY,
    corp_code     TEXT,
    company_name  TEXT NOT NULL,
    current_price INTEGER,
    market_cap    INTEGER,
    shares_out    INTEGER,
    rim_str       TEXT,
    charts_html   TEXT NOT NULL,
    report_md     TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """앱 시작 시 1회 호출 — 테이블 없으면 생성"""
    with _connect() as conn:
        conn.execute(_CREATE_TABLE_SQL)


def get_cached_report(stock_code: str) -> dict | None:
    """캐시된 리포트 반환. 한 번이라도 생성된 적이 있으면 기간에 상관없이 마지막 버전을 반환. 없으면 None"""
    with _connect() as conn:
        row = conn.execute(
            'SELECT * FROM reports WHERE stock_code = ?', (stock_code,)
        ).fetchone()

    if row is None:
        return None

    return {
        'company_name':  row['company_name'],
        'stock_code':    row['stock_code'],
        'current_price': row['current_price'],
        'market_cap':    row['market_cap'],
        'shares_out':    row['shares_out'],
        'rim_str':       row['rim_str'],
        'charts_html':   row['charts_html'],
        'report_md':     row['report_md'],
        'generated_at':  row['created_at'],
    }


def save_report(stock_code: str, corp_code: str, payload: dict) -> None:
    """분석 결과를 캐시에 저장 (UPSERT — stock_code 당 최신 1건만 유지)"""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO reports
                (stock_code, corp_code, company_name, current_price, market_cap,
                 shares_out, rim_str, charts_html, report_md, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                corp_code     = excluded.corp_code,
                company_name  = excluded.company_name,
                current_price = excluded.current_price,
                market_cap    = excluded.market_cap,
                shares_out    = excluded.shares_out,
                rim_str       = excluded.rim_str,
                charts_html   = excluded.charts_html,
                report_md     = excluded.report_md,
                created_at    = excluded.created_at
        """, (
            stock_code, corp_code, payload['company_name'], payload['current_price'],
            payload['market_cap'], payload['shares_out'], payload['rim_str'],
            payload['charts_html'], payload['report_md'], now_iso,
        ))
