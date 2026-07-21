import pandas as pd

try:
    import FinanceDataReader as fdr
except ImportError:
    import os
    os.system('pip install finance-datareader')
    import FinanceDataReader as fdr


def get_price_history(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """FinanceDataReader로 일봉 주가 히스토리 수집"""
    try:
        df = fdr.DataReader(stock_code, start_date, end_date)
        if df.empty:
            print(f"⚠️ 주가 데이터 없음: {stock_code}")
        return df
    except Exception as e:
        print(f"⚠️ 주가 데이터 수집 실패: {e}")
        return pd.DataFrame()


def get_kospi_history(start_date: str, end_date: str) -> pd.DataFrame:
    """FinanceDataReader로 KOSPI 지수 일봉 수집 (beta 계산용)"""
    try:
        return fdr.DataReader('KS11', start_date, end_date)
    except Exception as e:
        print(f"⚠️ KOSPI 데이터 수집 실패: {e}")
        return pd.DataFrame()
