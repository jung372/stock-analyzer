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


def _to_numeric_amount(df: pd.DataFrame, column: str = 'thstrm_amount') -> pd.DataFrame:
    """
    BUG FIX: astype(str) 누락으로 NaN 혼재 시 str.replace() 오류 발생
    → astype(str) 선적용 후 replace
    """
    df[column] = pd.to_numeric(
        df[column].astype(str).str.replace(',', ''), errors='coerce'
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
    """
    2년치 분기 재무제표 pivot (account_nm × period)

    DART 사업보고서(11011, '4Q')는 분기 단독 금액이 아닌 연간 누적 금액만 제공한다.
    손익계산서/포괄손익계산서(IS/CIS) 계정은 3분기 보고서(11014)의 누적 금액
    (thstrm_add_amount, 1~3분기 합산)을 연간 누적에서 차감해 4분기 단독 실적으로
    역산한다. 재무상태표(BS) 계정은 시점 잔액이라 역산 없이 연간 값을 그대로 사용.
    """
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

    if 'thstrm_add_amount' in df.columns:
        df_3q = df[df['period'].str.endswith('_3Q')].copy()
        df_3q = _to_numeric_amount(df_3q, 'thstrm_add_amount')
        cum_3q = df_3q.pivot_table(
            index='account_nm', columns='period',
            values='thstrm_add_amount', aggfunc='first'
        )
        cum_3q.columns = [c[:-len('_3Q')] for c in cum_3q.columns]

        for yr in range(start_yr, end_yr + 1):
            col_4q, col_3q_cum = f"{yr}_4Q", str(yr)
            if col_4q not in pivot_df.columns or col_3q_cum not in cum_3q.columns:
                continue
            cum = cum_3q[col_3q_cum].dropna()
            common = pivot_df.index.intersection(cum.index)
            pivot_df.loc[common, col_4q] = pivot_df.loc[common, col_4q] - cum.loc[common]

    return pivot_df.reindex(sorted(pivot_df.columns), axis=1)
