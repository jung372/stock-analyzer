import datetime

from dateutil.relativedelta import relativedelta

from data.kis_api        import (get_realtime_quote, get_quarterly_income_statement,
                                  isolate_quarters, get_balance_sheet, get_financial_ratios,
                                  annual_view)
from data.price_data     import get_price_history
from data.drive_reports  import get_broker_reports_for
from data.naver_cafe     import get_cafe_posts_for
from business.calculator import calc_all

QUARTERS_TO_SHOW = 9


def run_analysis(company_name: str, stock_code: str) -> dict:
    """전체 분석 파이프라인 실행 — 수집(KIS) → 계산 → 결과 dict 반환"""

    today          = datetime.datetime.today()
    today_str      = today.strftime('%Y-%m-%d')
    start_date_str = (today - relativedelta(years=10)).strftime('%Y-%m-%d')

    print(f"\n🔄 [{company_name}] 분석 시작...\n")

    # ── Tier 3: 데이터 수집 (KIS Open API)
    print("📡 KIS 실시간 시세 조회 중...")
    quote = get_realtime_quote(stock_code)
    current_price = quote['current_price']
    market_cap    = quote['market_cap']
    shares_out    = quote['shares_out']

    print("📈 주가 히스토리 수집 중...")
    df_price = get_price_history(stock_code, start_date_str, today_str)

    # 주가 폴백: KIS 시세 실패 시 FDR 마지막 종가 사용
    if current_price == 0 and not df_price.empty:
        current_price = int(df_price['Close'].iloc[-1])
        print(f"⚠️  KIS 시세 실패 → FDR 폴백 주가 적용: {current_price:,}원")

    print("📋 KIS 손익계산서/대차대조표/재무비율 조회 중 (분기 30개 기간, 단일 호출)...")
    df_income_cum = get_quarterly_income_statement(stock_code)   # 사업연도 누적 원본 (연간 요약용)
    df_income_iso = isolate_quarters(df_income_cum)              # 분기 단독 실적 (분기 표시용)
    df_balance    = get_balance_sheet(stock_code)
    df_ratio      = get_financial_ratios(stock_code)

    df_quarterly = df_income_iso.tail(QUARTERS_TO_SHOW).T if not df_income_iso.empty else df_income_iso

    df_fin_annual     = annual_view(df_income_cum)
    df_balance_annual = annual_view(df_balance)
    df_ratio_annual   = annual_view(df_ratio)

    print("📄 증권사 리포트(Google Drive) 탐색 중...")
    try:
        broker_reports = get_broker_reports_for(company_name)
    except Exception as e:
        print(f'[WARN] 증권사 리포트 수집 실패, 스킵: {e}')
        broker_reports = []

    print("💬 네이버 카페(주담통화/탐방) 탐색 중...")
    try:
        cafe_posts = get_cafe_posts_for(company_name, stock_code)
    except Exception as e:
        print(f'[WARN] 네이버 카페 게시글 수집 실패, 스킵: {e}')
        cafe_posts = []

    # ── Tier 2: 지표 계산
    metrics = calc_all(df_fin_annual, df_balance_annual, df_ratio_annual)

    print("\n✅ 데이터 수집 및 계산 완료\n")

    return {
        'company_name':   company_name,
        'stock_code':     stock_code,
        'current_price':  current_price,
        'market_cap':     market_cap,
        'shares_out':     shares_out,
        'per':            quote.get('per'),
        'pbr':            quote.get('pbr'),
        'eps':            quote.get('eps'),
        'bps':            quote.get('bps'),
        'foreign_ratio':  quote.get('foreign_ratio'),
        'df_price':       df_price,
        'df_fin':         df_fin_annual,
        'df_quarterly':   df_quarterly,
        'metrics':        metrics,
        'broker_reports': broker_reports,
        'cafe_posts':     cafe_posts,
    }
