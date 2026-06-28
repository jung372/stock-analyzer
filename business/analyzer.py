import datetime

from dateutil.relativedelta import relativedelta

from data.naver_api      import get_realtime_market_data
from data.dart_api       import get_dart_financials, get_dart_quarterly
from data.price_data     import get_price_history
from business.calculator import calc_all


def run_analysis(company_name: str, stock_code: str, corp_code: str) -> dict:
    """전체 분석 파이프라인 실행 — 수집 → 계산 → 결과 dict 반환"""

    today          = datetime.datetime.today()
    current_year   = today.year
    end_year       = current_year - 1
    start_year     = end_year - 9
    today_str      = today.strftime('%Y-%m-%d')
    start_date_str = (today - relativedelta(years=10)).strftime('%Y-%m-%d')

    print(f"\n🔄 [{company_name}] 분석 시작...\n")

    # ── Tier 3: 데이터 수집
    print("📡 실시간 시장 데이터 수집 중...")
    current_price, market_cap, shares_out = get_realtime_market_data(stock_code)

    print("📈 주가 히스토리 수집 중...")
    df_price = get_price_history(stock_code, start_date_str, today_str)

    # 주가 폴백: 네이버 API 실패 시 FDR 마지막 종가 사용
    if current_price == 0 and not df_price.empty:
        current_price = int(df_price['Close'].iloc[-1])
        print(f"⚠️  네이버 API 실패 → FDR 폴백 주가 적용: {current_price:,}원")

    print("📋 연간 재무제표 수집 중 (10년, 최대 30초)...")
    df_fin = get_dart_financials(corp_code, start_year, end_year)

    print("📋 분기 재무제표 수집 중...")
    df_quarterly = get_dart_quarterly(corp_code, end_year - 1, end_year)

    # ── Tier 2: 지표 계산
    metrics = calc_all(df_fin)

    print("\n✅ 데이터 수집 및 계산 완료\n")

    return {
        'company_name':  company_name,
        'stock_code':    stock_code,
        'current_price': current_price,
        'market_cap':    market_cap,
        'shares_out':    shares_out,
        'df_price':      df_price,
        'df_fin':        df_fin,
        'df_quarterly':  df_quarterly,
        'metrics':       metrics,
    }
