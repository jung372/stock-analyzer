import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
_APP_KEY = os.getenv('KIS_APP_KEY', '')
_APP_SECRET = os.getenv('KIS_APP_SECRET', '')
_BASE_URL = "https://openapi.koreainvestment.com:9443"  # 실전투자 도메인

_token = None
_token_expires_at = None

_INCOME_COLS = {
    'sale_account': '매출액', 'sale_cost': '매출원가', 'sale_totl_prfi': '매출총이익',
    'bsop_prti': '영업이익', 'thtr_ntin': '당기순이익',
}
_BALANCE_COLS = {'total_aset': '자산총계', 'total_lblt': '부채총계', 'total_cptl': '자본총계'}
_RATIO_COLS = {
    'roe_val': 'ROE', 'lblt_rate': '부채비율', 'grs': '매출액증가율',
    'bsop_prfi_inrt': '영업이익증가율', 'eps': 'EPS', 'bps': 'BPS',
}


def _get_token() -> str:
    """OAuth2 접근토큰 발급 (유효기간 24시간, 메모리 캐싱 후 재사용)"""
    global _token, _token_expires_at
    if _token and _token_expires_at and datetime.now() < _token_expires_at:
        return _token

    res = requests.post(
        f"{_BASE_URL}/oauth2/tokenP",
        json={"grant_type": "client_credentials", "appkey": _APP_KEY, "appsecret": _APP_SECRET},
        timeout=10,
    )
    res.raise_for_status()
    _token = res.json()["access_token"]
    _token_expires_at = datetime.now() + timedelta(hours=23)
    return _token


def _get(path: str, tr_id: str, params: dict) -> dict:
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {_get_token()}",
        "appkey": _APP_KEY,
        "appsecret": _APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }
    res = requests.get(f"{_BASE_URL}{path}", headers=headers, params=params, timeout=10)
    res.raise_for_status()
    body = res.json()
    if body.get('rt_cd') != '0':
        raise RuntimeError(f"KIS API 오류 ({tr_id}): {body.get('msg1')}")
    time.sleep(0.05)  # 실전투자 계좌 권장 호출 간격
    return body


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_realtime_quote(stock_code: str) -> dict:
    """
    KIS 주식현재가 시세 → 현재가/시가총액/상장주식수/PER/PBR/EPS/BPS/외국인지분율

    Naver 스크래핑(2회 순차 호출 + 시가총액 역산)을 단일 인증 호출로 대체.
    시가총액/상장주식수를 API가 직접 제공하므로 역산이 불필요함.
    """
    try:
        body = _get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
        )
    except Exception as e:
        print(f"⚠️ KIS 시세 조회 실패: {e}")
        return {'current_price': 0, 'market_cap': 0, 'shares_out': 0,
                'per': None, 'pbr': None, 'eps': None, 'bps': None, 'foreign_ratio': None}

    out = body.get('output', {})
    return {
        'current_price':  int(_to_float(out.get('stck_prpr')) or 0),
        'market_cap':      int((_to_float(out.get('hts_avls')) or 0) * 1e8),   # 억원 → 원
        'shares_out':      int(_to_float(out.get('lstn_stcn')) or 0),
        'per':             _to_float(out.get('per')),
        'pbr':             _to_float(out.get('pbr')),
        'eps':             _to_float(out.get('eps')),
        'bps':             _to_float(out.get('bps')),
        'foreign_ratio':   _to_float(out.get('hts_frgn_ehrt')),
    }


def _fetch_finance(stock_code: str, api_path: str, tr_id: str, div_key: str, col_map: dict) -> pd.DataFrame:
    """분기(1) 재무 데이터 공통 조회 → DataFrame (index=stac_yymm, 오름차순 정렬)"""
    body = _get(api_path, tr_id, {div_key: "1", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": stock_code})
    rows = body.get('output', [])
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    keep = ['stac_yymm'] + [c for c in col_map if c in df.columns]
    df = df[keep].rename(columns=col_map)
    for col in col_map.values():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.set_index('stac_yymm').sort_index()


def get_quarterly_income_statement(stock_code: str) -> pd.DataFrame:
    """
    분기 손익계산서 원본 (사업연도 누적 금액, DART와 동일한 방식) → 원 단위.

    12월(4Q) 행이 곧 해당 연도 전체 합계이므로, 연간 트렌드 요약은
    이 원본(누적치)에 annual_view()를 적용해서 뽑아야 한다.
    분기별 단독 실적이 필요하면 isolate_quarters()로 별도 변환한다.
    """
    df = _fetch_finance(
        stock_code, "/uapi/domestic-stock/v1/finance/income-statement",
        "FHKST66430200", "FID_DIV_CLS_CODE", _INCOME_COLS,
    )
    return df * 1e8 if not df.empty else df  # 억원 → 원


def isolate_quarters(df_cumulative: pd.DataFrame) -> pd.DataFrame:
    """
    사업연도 누적 금액 → 분기 단독 실적으로 변환 (같은 회계연도 내 직전 기간 차감).
    1분기는 누적=단독이라 그대로 둔다.

    주의: 조회 기간 창(window)의 첫 해에 직전 분기 데이터가 없으면(예: 가장 오래된
    연도가 4분기부터 시작) 그 행은 차감할 대상이 없어 누적치 그대로 남는다 —
    해당 연도의 "분기 단독" 값이 아니라 "그 시점까지의 누적치"이므로 주의해서 해석할 것.
    """
    if df_cumulative.empty:
        return df_cumulative

    isolated = df_cumulative.copy()
    year = pd.Series(df_cumulative.index, index=df_cumulative.index).str[:4]

    for _, idx in year.groupby(year).groups.items():
        idx = sorted(idx)  # 해당 연도 내 기간 오름차순 (1Q→2Q→3Q→4Q)
        prev_cum = None
        for i in idx:
            if prev_cum is not None:
                isolated.loc[i] = df_cumulative.loc[i] - prev_cum
            prev_cum = df_cumulative.loc[i]

    return isolated


def get_balance_sheet(stock_code: str) -> pd.DataFrame:
    """분기 대차대조표 → 시점 잔액이므로 역산 불필요, 그대로 사용"""
    df = _fetch_finance(
        stock_code, "/uapi/domestic-stock/v1/finance/balance-sheet",
        "FHKST66430100", "FID_DIV_CLS_CODE", _BALANCE_COLS,
    )
    return df * 1e8 if not df.empty else df  # 억원 → 원


def get_financial_ratios(stock_code: str) -> pd.DataFrame:
    """분기 재무비율 → ROE/부채비율/증가율/EPS/BPS (KIS가 이미 계산해서 제공)"""
    return _fetch_finance(
        stock_code, "/uapi/domestic-stock/v1/finance/financial-ratio",
        "FHKST66430300", "FID_DIV_CLS_CODE", _RATIO_COLS,
    )


def annual_view(df: pd.DataFrame) -> pd.DataFrame:
    """12월 결산(연간) 행만 추출, 연도(YYYY)로 재인덱싱"""
    if df.empty:
        return df
    annual = df[df.index.str.endswith('12')].copy()
    annual.index = annual.index.str[:4]
    return annual.sort_index()
