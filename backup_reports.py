import shutil
import pathlib
from datetime import datetime

# 파일 저장소(data/reports/) 전체를 Google Drive 동기화 폴더로 복사 (타임스탬프 폴더)
SRC_DIR  = pathlib.Path(__file__).parent / 'data' / 'reports'
DEST_DIR = pathlib.Path(r'G:\내 드라이브\02 주식\06 stock_analyzer_backup')


def backup() -> pathlib.Path | None:
    """data/reports/ 폴더를 Drive 동기화 폴더로 복사 (수동/자동 실행용)"""
    if not SRC_DIR.exists():
        print(f'[ERROR] 백업할 폴더가 없습니다: {SRC_DIR}')
        return None

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_path = DEST_DIR / f'reports_{timestamp}'
    shutil.copytree(SRC_DIR, dest_path)
    print(f'[INFO] 백업 완료: {dest_path}')
    return dest_path


if __name__ == '__main__':
    backup()
