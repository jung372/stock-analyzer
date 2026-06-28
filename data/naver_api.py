import re
import requests


def _parse_korean_amount(value: str) -> int:
    """
    '1,984조 8,116억' 같은 한국식 숫자 → 원 단위 정수 변환
    지원 단위: 조(10^12), 억(10^8), 만(10^4)
    """
    value = value.replace(',', '').replace(' ', '')
    total = 0
    for unit, multiplier in [('조', 10**12), ('억', 10**8), ('만', 10**4)]:
        m = re.search(rf'([\d.]+){unit}', value)
        if m:
            total += int(float(m.group(1)) * multiplier)
    # 단위 없는 숫자 (순수 숫자만 있는 경우)
    if total == 0:
        digits = re.sub(r'[^\d]', '', value)
        total = int(digits) if digits else 0
    return total


def get_realtime_market_data(stock_code: str) -> tuple:
    """
    네이버 금융 모바일 API → 현재 주가 / 시가총액 / 상장주식수

    BUG FIX:
      - /basic 엔드포인트에 marketValue/listCount 필드 없음 확인
      - /integration 엔드포인트의 totalInfos 리스트에서 시가총액 파싱
      - 발행주식수 = market_cap / price 로 역산
    Returns:
        (price, market_cap_won, shares) | (0, 0, 0) on failure
    """
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    }
    try:
        # 1) 현재 주가 ← /basic
        basic = requests.get(
            f"https://m.stock.naver.com/api/stock/{stock_code}/basic",
            headers=headers, timeout=10
        ).json()
        price = int(str(basic.get('closePrice', '0')).replace(',', ''))

        # 2) 시가총액 ← /integration totalInfos
        integration = requests.get(
            f"https://m.stock.naver.com/api/stock/{stock_code}/integration",
            headers=headers, timeout=10
        ).json()
        total_infos = integration.get('totalInfos', [])
        info_map    = {item['code']: item['value'] for item in total_infos}

        market_cap = _parse_korean_amount(info_map.get('marketValue', '0'))

        # 3) 발행주식수 역산 (price > 0 보장)
        shares = (market_cap // price) if price > 0 else 0

        return price, market_cap, shares

    except Exception as e:
        print(f"⚠️ 네이버 API 수집 실패: {e}")
        return 0, 0, 0
