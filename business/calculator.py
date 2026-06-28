import numpy as np
import pandas as pd


def _safe_series(df: pd.DataFrame, *names: str) -> pd.Series:
    """
    계정과목 추출 — 여러 후보명 순서대로 시도, 모두 없으면 0 시리즈 반환
    예) _safe_series(df, '당기순이익', '당기순이익(손실)')
    DART 공시마다 계정과목 표기가 다를 수 있어 다중 후보 지원
    """
    for name in names:
        if name in df.index:
            return df.loc[name].copy()
    return pd.Series(0, index=df.columns)


def calc_opm(op_profit: pd.Series, sales: pd.Series) -> pd.Series:
    return (op_profit / sales.replace(0, np.nan)) * 100


def calc_roe(net_profit: pd.Series, equity: pd.Series) -> pd.Series:
    return (net_profit / equity.replace(0, np.nan)) * 100


def calc_debt_ratio(liabilities: pd.Series, equity: pd.Series) -> pd.Series:
    return (liabilities / equity.replace(0, np.nan)) * 100


def calc_rim(equity: pd.Series, roe: pd.Series, ke: float = 0.08) -> float | None:
    """
    RIM 내재가치 = BV + (BV × (ROE - ke)) / ke
    ke: 자기자본비용 (기본값 8%)

    BUG FIX: equity=0 일 때 (계정과목 미매칭) 0.0 반환 → None 반환으로 수정
    """
    try:
        bv      = equity.iloc[-1]
        roe_val = roe.iloc[-1] / 100
        if pd.isna(bv) or pd.isna(roe_val) or bv == 0:
            return None
        return bv + (bv * (roe_val - ke)) / ke
    except Exception:
        return None


def calc_all(df_fin: pd.DataFrame) -> dict:
    """전체 재무 지표 일괄 계산 — df_fin이 비어 있으면 빈 dict 반환"""
    if df_fin.empty:
        return {}

    sales       = _safe_series(df_fin, '매출액', '수익(매출액)', '영업수익')
    op_profit   = _safe_series(df_fin, '영업이익', '영업이익(손실)')
    net_profit  = _safe_series(df_fin, '당기순이익', '당기순이익(손실)')
    equity      = _safe_series(df_fin, '자본총계', '자본합계')
    liabilities = _safe_series(df_fin, '부채총계', '부채합계')

    opm        = calc_opm(op_profit, sales)
    roe        = calc_roe(net_profit, equity)
    debt_ratio = calc_debt_ratio(liabilities, equity)
    rim_value  = calc_rim(equity, roe)

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
