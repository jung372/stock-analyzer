def _build_broker_excerpt_block(broker_reports: list) -> str:
    if not broker_reports:
        return "(제공된 증권사 리포트 없음 — 투자 아이디어/리스크는 귀하의 지식으로 직접 도출)"
    return "\n\n".join(f"### 리포트: {r['filename']}\n{r['text']}" for r in broker_reports)


def generate_llm_prompt(result: dict) -> str:
    """
    수집·계산된 데이터를 LLM 분석 프롬프트로 변환

    BUG FIX:
      - rim_str 미정의 상태에서 f-string 참조 오류 수정
      - 보고서 섹션 번호 체계 정리 (## 6이 ## 1 내부에 있던 오류)
    """
    name           = result['company_name']
    stock_code     = result['stock_code']
    current_price  = result['current_price']
    market_cap     = result['market_cap']
    shares_out     = result['shares_out']
    df_quarterly   = result['df_quarterly']
    rim_value      = result['metrics'].get('rim_value') if result['metrics'] else None
    broker_reports = result.get('broker_reports') or []

    # 포맷 변환
    rim_str    = f"{rim_value:,.0f} 원" if isinstance(rim_value, (int, float)) else "데이터 부족"
    mcap_str   = f"{market_cap:,.0f} 원" if market_cap > 0 else "[AI 계산 기입]"
    shares_str = f"{shares_out:,.0f} 주" if shares_out > 0 else "[AI 기입]"
    quarterly_str = (
        df_quarterly.to_markdown() if not df_quarterly.empty
        else "분기 데이터 수집 불가"
    )

    return f"""**[SYSTEM ROLE & INSTRUCTION]**
당신은 30년 경력의 월드클래스 가치투자 분석가입니다. 건조하고 냉소적이며 단호한 문체를 사용하십시오.

현재 분석 대상: {name} (종목코드: {stock_code})
현재 주가: {current_price:,.0f} 원
현재 시가총액: {mcap_str}
1차 추정 RIM 내재가치: {rim_str}

---
**[최근 9개 분기 핵심 재무 데이터]**
{quarterly_str}

**[기존 증권사 리포트 발췌 (최신 {len(broker_reports)}건)]**
{_build_broker_excerpt_block(broker_reports)}

---
**[STEP 1: 1차 심층 분석]** — 즉시 수행
{name}의 비즈니스 모델, 최근 재무 트렌드(분기 턴어라운드/훼손 포함),
매크로 이슈 연관성, 산업 내 위치를 브리핑하십시오.

**[STEP 2: 리스크 분석]** — 명령어: "추가 분석"
공매도, 대차잔고, 지배구조 리스크, 특허/소송, 경쟁사 단점 등 숨겨진 리스크를 전수 조사하십시오.

**[STEP 3: 최종 보고서]** — 명령어: "보고서 작성"

---
**[FINAL REPORT TEMPLATE]**

## 1. 사업현황

### 1) 주요지표
| 지표 | 수치 | 지표 | 수치 |
|---|---|---|---|
| **현재 주가** | {current_price:,.0f} 원 | **시가총액** | {mcap_str} |
| **대주주지분** | [AI 기입] | **외국인지분율** | [AI 기입] |
| **발행주식수** | {shares_str} | **수출비중** | [AI 기입] |
| **배당성향/수익률** | [AI 기입] | **PER / PBR** | [AI 기입] |

### 2) 주요사업내용
[비즈니스 모델 및 매출 비중 상세 설명]

### 3) 최근 분기 실적 및 주요 이벤트
[주가 급등락 시점 특정 및 분기 모멘텀 서술]

### 4) 기업 지배구조 및 임직원 현황
- 최대주주 및 주요주주 지분율
- 사내이사 현황 (직급, 연령, 출신)

### 5) 재무현황 요약
[매출/이익/부채 트렌드 핵심 요약 2줄]

## 2. 주요 고객 및 경쟁사 비교
[주요 고객사 리스트 및 경쟁사 대비 시장점유율]

## 3. 경쟁우위요소 (Economic Moat)
[해당 기업만의 해자 분석]

## 4. 투자 아이디어
[위 "기존 증권사 리포트 발췌"가 있다면 그 논거를 핵심 재료로 삼되, 귀하의 폭넓은 산업 지식을
함께 결합하여 더 입체적인 핵심 포인트 3~4가지 상세 기술. 본문에 특정 증권사명·리포트 제목을
직접 언급하지 말 것 (출처는 하단에 별도 첨부). 발췌가 없는 경우 귀하의 지식만으로 작성]

## 5. 기업가치 평가
- **RIM 내재가치:** {rim_str} (기본값) → [분기 데이터 반영 AI 재산출]
- **Forwarding POR:** [향후 2~3년 추정 실적 기반 산출]

## 6. 리스크 및 모니터링
[위 "기존 증권사 리포트 발췌"에 언급된 우려사항이 있다면 핵심 재료로 반영하되, 귀하의 산업
지식을 함께 결합해 더 종합적인 리스크 및 체크 변수 3가지 기술. 본문에 특정 증권사명·리포트
제목을 직접 언급하지 말 것]

## 7. 결론 및 최종 투자의견
[2~3줄 강력 요약 및 매수/중립/매도 의견]

---
이 프롬프트를 인식했다면, 즉시 **[STEP 1: 1차 심층 분석]**을 시작하십시오.
"""


def print_prompt(result: dict) -> None:
    prompt = generate_llm_prompt(result)
    print("\n" + "=" * 50)
    print("👇 아래 내용을 복사하여 AI에게 입력하세요\n")
    print(prompt)


def export_html_report(result: dict, charts_html: str, report_md: str) -> str:
    """분석 결과를 자체 완결형 HTML 파일로 저장하고 파일 경로를 반환한다."""
    import json
    import os
    import pathlib

    name          = result['company_name']
    stock_code    = result['stock_code']
    current_price = result['current_price']
    market_cap    = result['market_cap']
    shares_out    = result['shares_out']
    metrics       = result.get('metrics') or {}

    rim_value = metrics.get('rim_value')
    rim_str   = f"{rim_value:,.0f} 원" if isinstance(rim_value, (int, float)) else "데이터 부족"
    mcap_str  = f"{market_cap / 1e12:.1f}조 원" if market_cap > 0 else "-"
    shares_str = f"{shares_out:,.0f} 주" if shares_out > 0 else "-"

    # CSS 인라인 임베드
    css_path = pathlib.Path(__file__).parent.parent / "static" / "style.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} 투자 분석 보고서</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
{css}
  </style>
</head>
<body>
  <div class="container report-container">

    <header class="report-header">
      <div class="report-title-row">
        <h1>{name} <span class="stock-code">{stock_code}</span></h1>
        <div class="header-actions">
          <button onclick="window.print()" class="btn-print">🖨️ 인쇄 / PDF</button>
        </div>
      </div>
      <div class="kpi-bar">
        <div class="kpi">
          <span class="kpi-label">현재 주가</span>
          <span class="kpi-value">{current_price:,.0f} 원</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">시가총액</span>
          <span class="kpi-value">{mcap_str}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">발행주식수</span>
          <span class="kpi-value">{shares_str}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">RIM 내재가치</span>
          <span class="kpi-value">{rim_str}</span>
        </div>
      </div>
    </header>

    <section class="card chart-section">
      <h2>재무 분석 차트</h2>
      {charts_html}
    </section>

    <section class="card report-section">
      <h2>AI 투자 분석 보고서</h2>
      <div id="reportContent" class="report-body"></div>
    </section>

  </div>
  <script>
    const raw = {json.dumps(report_md, ensure_ascii=False)};
    document.getElementById('reportContent').innerHTML = marked.parse(raw);
  </script>
</body>
</html>"""

    out_dir = pathlib.Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    safe_name = name.replace(" ", "_")
    out_path = out_dir / f"report_{safe_name}.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
