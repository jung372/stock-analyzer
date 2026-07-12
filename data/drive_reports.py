import os
import re
import pathlib

from pypdf import PdfReader

DEFAULT_BASE_FOLDER = r"G:\내 드라이브\02 주식\02 섹터 및 종목 내용 정리"
MAX_FILES_PER_STOCK  = 5      # 최신 mtime 순 상위 5개 PDF만 사용
MAX_PAGES_PER_FILE   = 2      # 파일당 첫 2페이지만 (핵심 결론이 보통 앞부분에 요약됨)
MAX_CHARS_PER_FILE   = 3000   # 파일당 텍스트 상한


def get_base_folder() -> str:
    """환경변수 GDRIVE_SECTOR_FOLDER 우선, 없으면 기본 경로 폴백"""
    return os.getenv('GDRIVE_SECTOR_FOLDER', DEFAULT_BASE_FOLDER)


def _normalize(name: str) -> str:
    """폴더명 정규화: 끝의 (종목코드) 괄호 제거 + 공백/대소문자 정리"""
    return re.sub(r'\([^)]*\)\s*$', '', name).strip().lower()


def find_stock_folder(company_name: str, base_folder: str | None = None) -> pathlib.Path | None:
    """
    company_name과 일치하는 하위 폴더를 base_folder에서 탐색.
    완전일치 우선, 없으면 부분일치(양방향 substring)로 재시도.
    - base_folder가 존재하지 않거나 매칭되는 폴더가 없으면 None (호출 측에서 skip)
    """
    base = pathlib.Path(base_folder or get_base_folder())
    if not base.exists():
        print(f'[WARN] Drive 폴더 없음 — 스킵: {base}')
        return None

    target = _normalize(company_name)
    if not target:
        return None

    candidates = [c for c in base.iterdir() if c.is_dir()]

    for c in candidates:                      # 1차: 완전 일치
        if _normalize(c.name) == target:
            return c
    for c in candidates:                      # 2차: 부분 일치 (양방향)
        name = _normalize(c.name)
        if name and (target in name or name in target):
            return c
    return None


def extract_broker_reports(folder: pathlib.Path) -> list[dict]:
    """폴더 내 PDF에서 텍스트 추출. 최신 수정일 순, 개별 파일 실패는 skip하고 계속 진행."""
    pdfs = sorted(folder.glob('*.pdf'), key=lambda p: p.stat().st_mtime, reverse=True)
    pdfs = pdfs[:MAX_FILES_PER_STOCK]

    reports = []
    for pdf_path in pdfs:
        try:
            reader = PdfReader(str(pdf_path))
            pages  = reader.pages[:MAX_PAGES_PER_FILE]
            text   = "\n".join(p.extract_text() or "" for p in pages).strip()
        except Exception as e:
            print(f'[WARN] PDF 읽기 실패, 스킵: {pdf_path.name} ({e})')
            continue

        if not text:
            continue

        reports.append({'filename': pdf_path.stem, 'text': text[:MAX_CHARS_PER_FILE]})

    return reports


def get_broker_reports_for(company_name: str, base_folder: str | None = None) -> list[dict]:
    """analyzer.py에서 호출하는 단일 진입점. 항상 list 반환 (매칭 실패/리포트 없음 → 빈 리스트)."""
    folder = find_stock_folder(company_name, base_folder)
    if folder is None:
        print(f'[INFO] 증권사 리포트 폴더 매칭 안됨: {company_name}')
        return []

    reports = extract_broker_reports(folder)
    if reports:
        print(f'[INFO] 증권사 리포트 {len(reports)}건 추출: {folder.name}')
    else:
        print(f'[INFO] 리포트 폴더는 있으나 PDF 없음: {folder.name}')
    return reports
