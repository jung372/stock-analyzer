import datetime

from dateutil.relativedelta import relativedelta

from data.naver_api      import get_realtime_market_data
from data.dart_api       import get_dart_financials, get_dart_quarterly
from data.price_data     import get_price_history
from data.drive_reports  import get_broker_reports_for
from business.calculator import calc_all


def run_analysis(company_name: str, stock_code: str, corp_code: str) -> dict:
    """전체 분석 파이프라인 실행 — 수집 → 계산 → 결과 dict 반환"""

    today          = datetime.datetime.today()
    current_year   = today.year
    end_year       = current_year - 1          # 연간: 당해 사업보고서 미공시 → 직전 연도까지
    start_year     = end_year - 9
    today_str      = today.strftime('%Y-%m-%d')
    start_date_str = (today - relativedelta(years=10)).strftime('%Y-%m-%d')

    # 분기: 최근 9개 분기 표시 → 3개년 조회 후 최신 9개 분기만 슬라이싱
    # (당해연도까지 포함해 최신 공시 분기 반영, 미공시 분기는 내부에서 자동 skip)
    QUARTERS_TO_SHOW = 9
    q_start_year     = current_year - 2
    q_end_year       = current_year

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

    print(f"📋 분기 재무제표 수집 중 (최근 {QUARTERS_TO_SHOW}개 분기)...")
    df_quarterly = get_dart_quarterly(corp_code, q_start_year, q_end_year)
    # 최신 9개 분기만 유지 (컬럼은 시간순 정렬되어 있음 → 뒤에서 9개)
    if not df_quarterly.empty and df_quarterly.shape[1] > QUARTERS_TO_SHOW:
        df_quarterly = df_quarterly.iloc[:, -QUARTERS_TO_SHOW:]

    print("📄 증권사 리포트(Google Drive) 탐색 중...")
    try:
        broker_reports = get_broker_reports_for(company_name)
    except Exception as e:
        print(f'[WARN] 증권사 리포트 수집 실패, 스킵: {e}')
        broker_reports = []

    # ── Tier 2: 지표 계산
    metrics = calc_all(df_fin)

    print("\n✅ 데이터 수집 및 계산 완료\n")

    return {
        'company_name':   company_name,
        'stock_code':     stock_code,
        'current_price':  current_price,
        'market_cap':     market_cap,
        'shares_out':     shares_out,
        'df_price':       df_price,
        'df_fin':         df_fin,
        'df_quarterly':   df_quarterly,
        'metrics':        metrics,
        'broker_reports': broker_reports,
    }
