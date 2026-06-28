import os
import webbrowser
from dotenv import load_dotenv

load_dotenv()

from business.analyzer      import run_analysis
from presentation.charts    import generate_plotly_html
from presentation.report    import export_html_report
from llm.claude_client      import generate_report


def main():
    print("=" * 50)
    print("가치투자 포렌식 분석 엔진 V3.0")
    print("=" * 50 + "\n")

    company_name = input("분석할 기업명을 입력하세요 (예: 삼성전자): ").strip()
    stock_code   = input(f"{company_name}의 종목코드 (예: 005930): ").strip()
    corp_code    = input(f"{company_name}의 DART 고유번호 (예: 00126380): ").strip()

    print("\n[1/3] 재무 데이터 수집 및 계산 중...")
    result = run_analysis(company_name, stock_code, corp_code)

    print("[2/3] 차트 생성 중...")
    charts_html = generate_plotly_html(result)

    print("[3/3] AI 보고서 생성 중 (약 1~2분 소요)...")
    report_md = generate_report(result)

    out_path = export_html_report(result, charts_html, report_md)
    print(f"\n보고서 저장 완료: {out_path}")

    webbrowser.open(f"file:///{out_path.replace(chr(92), '/')}")


if __name__ == "__main__":
    main()
