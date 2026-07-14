import pandas as pd


def calc_opm(op_profit: pd.Series, sales: pd.Series) -> pd.Series:
    return (op_profit / sales.replace(0, float('nan'))) * 100


def calc_rim(bps: pd.Series, roe: pd.Series, ke: float = 0.08) -> float | None:
    """
    RIM 주당 내재가치 = BPS + (BPS × (ROE - ke)) / ke
    ke: 자기자본비용 (기본값 8%)

    주가와 직접 비교해야 하므로 총자본이 아닌 주당순자산(BPS) 기준으로 계산한다.
    """
    try:
        bv      = bps.iloc[-1]
        roe_val = roe.iloc[-1] / 100
        if pd.isna(bv) or pd.isna(roe_val) or bv == 0:
            return None
        return bv + (bv * (roe_val - ke)) / ke
    except Exception:
        return None


def calc_all(df_income_annual: pd.DataFrame, df_balance_annual: pd.DataFrame, df_ratio_annual: pd.DataFrame) -> dict:
    """
    연간(12월 결산 누적치) 지표 일괄 계산.

    ROE/부채비율/증가율은 KIS 재무비율 API가 이미 계산해서 제공하므로 그대로 사용하고,
    OPM만 손익계산서 원본(영업이익/매출액)으로 직접 계산한다.
    (DART 시절의 계정과목 이름 매칭(_safe_series)이 더 이상 필요 없음 — KIS 응답은 컬럼명이 고정)
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
    rim_value  = calc_rim(bps, roe)

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
    }
