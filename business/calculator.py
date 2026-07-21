import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_RF  = float(os.getenv('RIM_RF',  '0.028'))
_ERP = float(os.getenv('RIM_ERP', '0.055'))
_G   = float(os.getenv('RIM_G',   '0.030'))


def calc_opm(op_profit: pd.Series, sales: pd.Series) -> pd.Series:
    return (op_profit / sales.replace(0, float('nan'))) * 100


def calc_rim(
    bps: pd.Series,
    roe: pd.Series,
    beta: float = 1.0,
    rf: float | None = None,
    erp: float | None = None,
    g: float | None = None,
) -> tuple[float | None, float]:
    """
    RIM 주당 내재가치 = BPS + (BPS × (ROE_avg - ke)) / (ke - g)

    ke = rf + beta × ERP  (CAPM)
    ROE_avg = 최근 4개년 평균 ROE (데이터 부족 시 가용 데이터 전체 평균)
    g = 영구성장률 (고정)

    반환: (내재가치, 실제 사용된 ke)
    """
    rf  = _RF  if rf  is None else rf
    erp = _ERP if erp is None else erp
    g   = _G   if g   is None else g

    ke = rf + beta * erp

    if ke <= g:
        return None, ke

    try:
        bv = bps.iloc[-1]
        roe_vals = roe.dropna()
        if len(roe_vals) == 0:
            return None, ke
        roe_avg = roe_vals.iloc[-4:].mean() / 100

        if pd.isna(bv) or pd.isna(roe_avg) or bv == 0:
            return None, ke

        value = bv + (bv * (roe_avg - ke)) / (ke - g)
        return value, ke
    except Exception:
        return None, ke


def calc_all(
    df_income_annual: pd.DataFrame,
    df_balance_annual: pd.DataFrame,
    df_ratio_annual: pd.DataFrame,
    beta: float = 1.0,
) -> dict:
    """
    연간(12월 결산 누적치) 지표 일괄 계산.

    ROE/부채비율/증가율은 KIS 재무비율 API가 이미 계산해서 제공하므로 그대로 사용하고,
    OPM만 손익계산서 원본(영업이익/매출액)으로 직접 계산한다.
    """
    if df_income_annual.empty or df_ratio_annual.empty:
        return {}

    sales       = df_income_annual['매출액']
    op_profit   = df_income_annual['영업이익']
    net_profit  = df_income_annual['당기순이익']
    equity      = df_balance_annual['자본총계'] if not df_balance_annual.empty else pd.Series(dtype=float)
    liabilities = df_balance_annual['부채총계'] if not df_balance_annual.empty else pd.Series(dtype=float)
    bps         = df_ratio_annual['BPS']

    opm        = calc_opm(op_profit, sales)
    roe        = df_ratio_annual['ROE']
    debt_ratio = df_ratio_annual['부채비율']
    rim_value, rim_ke = calc_rim(bps, roe, beta=beta)

    return {
        'sales':       sales,
        'op_profit':   op_profit,
        'net_profit':  net_profit,
        'equity':      equity,
        'liabilities': liabilities,
        'opm':         opm,
        'roe':         roe,
        'debt_ratio':  debt_ratio,
        'rim_value':   rim_value,
        'rim_ke':      rim_ke,
    }
