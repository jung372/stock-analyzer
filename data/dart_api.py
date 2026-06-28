import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
_API_KEY = os.getenv('DART_API_KEY', '')
_BASE_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"


def _fetch_one(corp_code: str, bsns_year: str, reprt_code: str) -> pd.DataFrame:
    """단일 기간 재무제표 요청 → DataFrame 반환 (실패 시 빈 DataFrame)"""
    params = {
        'crtfc_key':  _API_KEY,
        'corp_code':  corp_code,
        'bsns_year':  bsns_year,
        'reprt_code': reprt_code,
    }
    try:
        res = requests.get(_BASE_URL, params=params, timeout=10).json()
        if res.get('status') == '000':
            return pd.DataFrame(res['list'])
    except Exception as e:
        print(f"⚠️ DART 요청 실패 ({bsns_year} / {reprt_code}): {e}")
    return pd.DataFrame()


def _to_numeric_amount(df: pd.DataFrame) -> pd.DataFrame:
    """
    BUG FIX: astype(str) 누락으로 NaN 혼재 시 str.replace() 오류 발생
    → astype(str) 선적용 후 replace
    """
    df['thstrm_amount'] = pd.to_numeric(
        df['thstrm_amount'].astype(str).str.replace(',', ''), errors='coerce'
    )
    return df


def get_dart_financials(corp_code: str, start_yr: int, end_yr: int) -> pd.DataFrame:
    """10년치 연간 재무제표 pivot (account_nm × bsns_year)"""
    all_data = []
    for yr in range(start_yr, end_yr + 1):
        df = _fetch_one(corp_code, str(yr), '11011')
        if not df.empty:
            all_data.append(df)
        time.sleep(0.12)

    if not all_data:
        return pd.DataFrame()

    df = _to_numeric_amount(pd.concat(all_data, ignore_index=True))
    return df.pivot_table(
        index='account_nm', columns='bsns_year',
        values='thstrm_amount', aggfunc='first'
    )


def get_dart_quarterly(corp_code: str, start_yr: int, end_yr: int) -> pd.DataFrame:
    """2년치 분기 재무제표 pivot (account_nm × period)"""
    reports = {'1Q': '11013', '2Q': '11012', '3Q': '11014', '4Q': '11011'}
    all_data = []

    for yr in range(start_yr, end_yr + 1):
        for term, r_code in reports.items():
            df = _fetch_one(corp_code, str(yr), r_code)
            if not df.empty:
                df['period'] = f"{yr}_{term}"
                all_data.append(df)
            time.sleep(0.12)

    if not all_data:
        return pd.DataFrame()

    df = _to_numeric_amount(pd.concat(all_data, ignore_index=True))
    pivot_df = df.pivot_table(
        index='account_nm', columns='period',
        values='thstrm_amount', aggfunc='first'
    )
    return pivot_df.reindex(sorted(pivot_df.columns), axis=1)
