"""
네이버 카페(주담통화/탐방) 게시글 수집을 위한 1회성 로그인 스크립트.

비밀번호는 어디에도 저장하지 않는다 — 브라우저 창을 직접 띄워 사용자가 본인 계정으로
수동 로그인(2단계 인증/캡차 포함)하면, 로그인 완료 후의 쿠키(세션)만 로컬 파일로 저장한다.
(웹 UI에서 "네이버 카페 로그인" 팝업의 "예"를 선택했을 때도 동일한 로직이 실행된다 —
data/naver_cafe.py의 run_login_flow()를 공용으로 사용.)

사용법:
    python naver_login_setup.py

세션이 만료되면(콘솔에서 "네이버 세션 만료" 경고를 보게 되면) 이 스크립트를 다시 실행한다.
"""
from data.naver_cafe import LOGIN_TIMEOUT_SEC, SESSION_PATH, run_login_flow


def main():
    print(f"[안내] 브라우저 창에서 네이버에 직접 로그인해주세요.")
    print("[안내] 2단계 인증/캡차가 뜨면 그대로 진행하시면 됩니다.")
    print(f"[안내] 로그인 완료를 최대 {LOGIN_TIMEOUT_SEC}초 동안 자동으로 기다립니다...")

    ok = run_login_flow(headless=False)

    if ok:
        print(f"[완료] 세션 저장됨 → {SESSION_PATH}")
    else:
        print("[실패] 로그인이 감지되지 않았거나 이미 다른 로그인이 진행 중입니다. 다시 실행해주세요.")


if __name__ == "__main__":
    main()
