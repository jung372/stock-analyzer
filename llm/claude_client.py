import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
_client = Anthropic()  # ANTHROPIC_API_KEY 환경변수 자동 로드


def generate_report(result: dict) -> str:
    """
    수집된 재무 데이터를 Claude API에 전송 → 완성된 보고서 마크다운 반환
    model: claude-sonnet-4-6
    """
    prompt = _build_prompt(result)
    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def _build_prompt(result: dict) -> str:
    name          = result['company_name']
    stock_code    = result['stock_code']
    current_price = result['current_price']
    market_cap    = result['market_cap']
    shares_out    = result['shares_out']
    df_quarterly  = result['df_quarterly']
    metrics       = result['metrics']
    df_fin        = result['df_fin']

    rim_value  = metrics.get('rim_value') if metrics else None
    rim_str    = f"{rim_value:,.0f} 원" if isinstance(rim_value, float) else "계산 불가"
    mcap_str   = f"{market_cap / 1e12:.1f}조 원" if market_cap > 0 else "수집 불가"
    shares_str = f"{shares_out:,.0f} 주" if shares_out > 0 else "수집 불가"
    price_str  = f"{current_price:,.0f} 원"

    # 연간 주요 지표 요약
    annual_summary = ""
    if metrics and not df_fin.empty:
        cols = df_fin.columns.tolist()[-5:]  # 최근 5년만
        lines = []
        for label, key in [('OPM(%)', 'opm'), ('ROE(%)', 'roe'), ('부채비율(%)', 'debt_ratio')]:
            vals = metrics[key][cols].round(1).to_dict()
            lines.append(f"{label}: " + ", ".join(f"{k}={v}" for k, v in vals.items()))
        annual_summary = "\n".join(lines)

    quarterly_str = df_quarterly.to_markdown() if not df_quarterly.empty else "수집 불가"

    return f"""당신은 30년 경력의 월드클래스 가치투자 분석가입니다.
아래 재무 데이터를 바탕으로 [보고서 양식]에 맞춰 완전한 투자 분석 보고서를 즉시 작성하십시오.
건조하고 냉소적이며 단호한 문체를 사용하고, 모든 섹션을 빠짐없이 채우십시오.
[AI 기입] 표시 항목은 귀하의 지식을 활용하여 실제 값을 기입하십시오.

---
[수집 데이터]
기업명: {name} (종목코드: {stock_code})
현재 주가: {price_str}
시가총액: {mcap_str}
발행주식수: {shares_str}
RIM 내재가치 (ke=8%): {rim_str}

[연간 수익성/안정성 지표 (최근 5년)]
{annual_summary}

[최근 2개년 분기별 재무제표]
{quarterly_str}

---
[보고서 양식 - 아래 구조 그대로 작성, 섹션 누락 금지]

## 1. 사업현황

### 1) 주요지표
| 지표 | 수치 | 지표 | 수치 |
|---|---|---|---|
| **현재 주가** | {price_str} | **시가총액** | {mcap_str} |
| **대주주지분** | [AI 기입] | **외국인지분율** | [AI 기입] |
| **발행주식수** | {shares_str} | **수출비중** | [AI 기입] |
| **배당성향/수익률** | [AI 기입] | **PER / PBR** | [AI 기입] |

### 2) 주요사업내용
[{name}의 핵심 비즈니스 모델 및 사업부별 매출 비중을 상세히 기술]

### 3) 최근 분기 실적 및 주요 이벤트
[위 분기 데이터 기반으로 실적 모멘텀 분석. 턴어라운드/훼손 여부 판단]

### 4) 기업 지배구조 및 임직원 현황
- **최대주주 및 주요주주 지분율**: [AI 기입]
- **사내이사 현황**: [AI 기입]

### 5) 재무현황 요약
[연간 지표 기반 매출/이익/부채 트렌드 핵심 2줄 요약]

## 2. 주요 고객 및 경쟁사 비교
[주요 고객사 및 경쟁사 대비 포지셔닝 분석]

## 3. 경쟁우위요소 (Economic Moat)
[{name}만의 지속 가능한 경쟁 해자를 구체적으로 분석]

## 4. 투자 아이디어
[핵심 투자 포인트 3~4가지를 번호 목록으로 상세 기술]

## 5. 기업가치 평가
- **RIM 내재가치**: {rim_str} (ke=8% 적용) → [현재 주가 대비 괴리율 계산 및 해석]
- **Forwarding POR**: [분기 모멘텀 반영 향후 2~3년 추정 실적 기반 산출]
- **PER/PBR 밴드 분석**: [AI 기입]

## 6. 리스크 및 모니터링
1. [리스크 1]
2. [리스크 2]
3. [리스크 3]

## 7. 결론 및 최종 투자의견
[2~3줄 강력한 요약 및 매수/중립/매도 의견과 목표주가 제시]
"""
