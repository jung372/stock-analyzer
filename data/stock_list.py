import io
import json
import pathlib
import time
import zipfile
import xml.etree.ElementTree as ET
import requests

CACHE_PATH = pathlib.Path(__file__).parent / 'corps_cache.json'
CACHE_TTL  = 7 * 24 * 3600  # 7일


def load_corp_list(api_key: str) -> list:
    """DART 상장 기업 목록 반환 (캐시 우선, 7일 이후 재다운로드)"""
    if CACHE_PATH.exists() and (time.time() - CACHE_PATH.stat().st_mtime) < CACHE_TTL:
        return json.loads(CACHE_PATH.read_text(encoding='utf-8'))

    print('[INFO] DART 기업 목록 다운로드 중...')
    corps = _fetch_from_dart(api_key)
    CACHE_PATH.write_text(json.dumps(corps, ensure_ascii=False, indent=None), encoding='utf-8')
    print(f'[INFO] 기업 목록 캐시 저장 완료: {len(corps)}개')
    return corps


def _fetch_from_dart(api_key: str) -> list:
    url  = f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}'
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read('CORPCODE.xml')

    root   = ET.fromstring(xml_bytes.decode('utf-8'))
    result = []
    for item in root.findall('list'):
        stock_code = (item.findtext('stock_code') or '').strip()
        if not stock_code:
            continue
        result.append({
            'corp_name':  (item.findtext('corp_name') or '').strip(),
            'stock_code': stock_code,
            'corp_code':  (item.findtext('corp_code') or '').strip(),
        })
    return result


def search_corps(corps: list, query: str, limit: int = 10) -> list:
    """이름 또는 코드로 기업 검색 (이름 전방 일치 우선)"""
    q = query.strip().lower()
    if not q:
        return []
    starts, contains, by_code = [], [], []
    for c in corps:
        name = c['corp_name'].lower()
        code = c['stock_code']
        if name.startswith(q):
            starts.append(c)
        elif q in name:
            contains.append(c)
        elif code.startswith(q):
            by_code.append(c)
    return (starts + contains + by_code)[:limit]
