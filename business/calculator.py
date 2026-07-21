import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_RF  = float(os.getenv('RIM_RF',  '0.028'))
_ERP = float(os.getenv('RIM_ERP', '0.055'))
_G   = float(os.getenv('RIM_G',   '0.030'))


def calc_opm(op_profit: pd.Series, sales: pd.Series) -> pd.Series:
    return (op_profit / sales.replace(0, float('nan'))) * 100


def calc_derived_roe(
    net_profit: pd.Series,
    total_asset: pd.Series,
    equity: pd.Series,
) -> float | None:
    """
    ROA 장기평균 × 최근 2년 레버리지로 ROE를 파생 계산 (DuPont 분해).

    파생 ROE(%) = ROA_avg(%) × Leverage_2yr
    ROA_avg     = 가용 전체 기간 평균(순이익/자산총계 × 100)
    Leverage    = 자산총계 / 자본총계 (최근 2개년 평균)
    """
    try:
        common = net_profit.index.intersection(total_asset.index).intersection(equity.index)
        if len(common) == 0:
            return None

        roa       = (net_profit.loc[common] / total_asset.loc[common] * 100).dropna()
        lev       = (total_asset.loc[common] / equity.loc[common]).dropna()

        if len(roa) == 0 or len(lev) == 0:
            return None

        roa_avg   = roa.mean()                   # 가용 전체 기간(최대 8년) 평균
        lev_2yr   = lev.iloc[-2:].mean()         # 최근 2개년 평균

        derived = roa_avg * lev_2yr
        return float(derived)
    except Exception:
        return None


def calc_rim(
    bps_val: float,
    roe_pct: float,
    beta: float = 1.0,
    rf: float | None = None,
    erp: float | None = None,
    g: float | None = None,
) -> tuple[float | None, float]:
    """
    RIM 주당 내재가치 = BPS + (BPS × (ROE - ke)) / (ke - g)

    ke = rf + beta × ERP  (CAPM)
    g  = 영구성장률 (고정)

    bps_val : 주당순자산 (원)
    roe_pct : calc_derived_roe()로 산출한 파생 ROE (% 단위, 예: 10.64)

    반환: (내재가치, 실제 사용된 ke)
    """
    rf  = _RF  if rf  is None else rf
    erp = _ERP if erp is None else erp
    g   = _G   if g   is None else g

    ke = rf + beta * erp

    if ke <= g:
        return None, ke

    try:
        roe_dec = roe_pct / 100
        if pd.isna(bps_val) or pd.isna(roe_dec) or bps_val == 0:
            return None, ke

        value = bps_val + (bps_val * (roe_dec - ke)) / (ke - g)
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
    RIM용 ROE는 ROA 장기평균 × 최근 2년 레버리지로 파생 계산한다.
    """
    if df_income_annual.empty or df_ratio_annual.empty:
        return {}

    sales       = df_income_annual['매출액']
    op_profit   = df_income_annual['영업이익']
    net_profit  = df_income_annual['당기순이익']
    total_asset = df_balance_annual['자산총계']   if not df_balance_annual.empty else pd.Series(dtype=float)
    equity      = df_balance_annual['자본총계']   if not df_balance_annual.empty else pd.Series(dtype=float)
    liabilities = df_balance_annual['부채총계']   if not df_balance_annual.empty else pd.Series(dtype=float)
    bps         = df_ratio_annual['BPS']

    opm        = calc_opm(op_profit, sales)
    roe        = df_ratio_annual['ROE']
    debt_ratio = df_ratio_annual['부채비율']

    derived_roe = calc_derived_roe(net_profit, total_asset, equity)
    bps_val     = float(bps.iloc[-1]) if not bps.empty else None

    if derived_roe is not None and bps_val is not None:
        rim_value, rim_ke = calc_rim(bps_val, derived_roe, beta=beta)
    else:
        rim_value, rim_ke = None, _RF + beta * _ERP

    return {
        'sales':        sales,
        'op_profit':    op_profit,
        'net_profit':   net_profit,
        'equity':       equity,
        'liabilities':  liabilities,
        'opm':          opm,
        'roe':          roe,
        'debt_ratio':   debt_ratio,
        'rim_value':    rim_value,
        'rim_ke':       rim_ke,
        'rim_roe_used': derived_roe,  # 디버깅/프롬프트 표시용
    }
