import shutil
import pathlib
from datetime import datetime

SRC_PATH = pathlib.Path(__file__).parent / 'data' / 'reports.db'
DEST_DIR = pathlib.Path(r'G:\내 드라이브\02 주식\06 stock_analyzer_backup')


def backup() -> pathlib.Path | None:
    """reports.db를 Google Drive 동기화 폴더로 복사 (타임스탬프 파일명, 수동 실행용)"""
    if not SRC_PATH.exists():
        print(f'[ERROR] 백업할 파일이 없습니다: {SRC_PATH}')
        return None

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_path = DEST_DIR / f'reports_{timestamp}.db'
    shutil.copy2(SRC_PATH, dest_path)
    print(f'[INFO] 백업 완료: {dest_path}')
    return dest_path


if __name__ == '__main__':
    backup()
