import os
import pandas as pd
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
        max_tokens=16384,   # 증권사 리포트 발췌 추가로 응답이 길어져 8096에서 상향
        messages=[{"role": "user", "content": prompt}]
    )
    report_md = message.content[0].text
    # 재무제표 표는 LLM이 재생성하지 않고 코드가 정확히 주입 (숫자 정확성 보증)
    report_md = _inject_financials(report_md, result)
    report_md = _append_source_footer(report_md, result.get('broker_reports') or [])
    report_md = _append_cafe_source_footer(report_md, result.get('cafe_posts') or [])
    return report_md


def _append_source_footer(report_md: str, broker_reports: list) -> str:
    """
    증권사 리포트 출처는 본문에 직접 언급하지 않도록 프롬프트로 지시하고,
    대신 LLM이 아닌 코드가 직접 파일명 목록을 하단에 append (정확성 보장).
    """
    if not broker_reports:
        return report_md
    sources = "\n".join(f"- {r['filename']}" for r in broker_reports)
    return f"{report_md}\n\n---\n**참고: 증권사 리포트 출처**\n{sources}\n"


def _build_broker_excerpt_block(broker_reports: list) -> str:
    if not broker_reports:
        return "(제공된 증권사 리포트 없음 — 투자 아이디어/리스크는 귀하의 지식으로 직접 도출)"
    return "\n\n".join(f"### 리포트: {r['filename']}\n{r['text']}" for r in broker_reports)


def _append_cafe_source_footer(report_md: str, cafe_posts: list) -> str:
    """
    카페 게시글 출처도 본문에 직접 언급하지 않도록 프롬프트로 지시하고,
    대신 LLM이 아닌 코드가 직접 제목+링크를 하단에 append (정확성 보장).
    """
    if not cafe_posts:
        return report_md
    sources = "\n".join(f"- [{p['board']}] {p['title']} ({p['date']}) — {p['url']}" for p in cafe_posts)
    return f"{report_md}\n\n---\n**참고: 카페(주담통화/탐방) 출처**\n{sources}\n"


def _build_cafe_excerpt_block(cafe_posts: list) -> str:
    if not cafe_posts:
        return "(제공된 카페 IR콜/탐방 메모 없음 — 투자 아이디어/리스크는 귀하의 지식으로 직접 도출)"
    return "\n\n".join(
        f"### [{p['board']}] {p['title']} ({p['date']}, {p['author']})\n{p['text']}"
        for p in cafe_posts
    )


def _inject_financials(report_md: str, result: dict) -> str:
    """'## 2. 재무제표 현황' 섹션의 해설 뒤(다음 '## ' 섹션 앞)에 실제 재무제표 표를 삽입.

    LLM에게 표를 그리게 하지 않고(수치 부정확 위험) 코드가 위치 기반으로 삽입한다.
    LLM이 실수로 남길 수 있는 {{FINANCIALS_TABLE}}/{FINANCIALS_TABLE} 자리표시자는 제거한다.
    """
    import re
    block = _build_financials_block(result)

    # 혹시 남아있을 자리표시자 토큰 제거 (홑/겹중괄호 모두)
    report_md = re.sub(r'\{\{?\s*FINANCIALS_TABLE\s*\}?\}', '', report_md)

    m = re.search(r'^##\s*2\..*재무제표.*$', report_md, flags=re.MULTILINE)
    if not m:
        # 헤더를 못 찾으면 보고서 끝에 별도 섹션으로 덧붙임
        return f"{report_md.rstrip()}\n\n## 재무제표 현황\n\n{block}\n"

    # 섹션 2 다음의 '## ' 헤더 위치를 찾아 그 앞에 표 삽입 (해설 뒤에 위치)
    nxt = re.search(r'^##\s', report_md[m.end():], flags=re.MULTILINE)
    if nxt:
        insert_pos = m.end() + nxt.start()
        return report_md[:insert_pos].rstrip() + '\n\n' + block + '\n\n' + report_md[insert_pos:]
    return report_md.rstrip() + '\n\n' + block + '\n'


def _fmt_eok(v) -> str:
    """원 단위 값 → 억원 콤마 문자열 (지수표기 방지). NaN은 '-'."""
    return '-' if pd.isna(v) else f'{v / 1e8:,.0f}'


def _fmt_pct(v) -> str:
    return '-' if pd.isna(v) else f'{v:.1f}'


def _build_financials_block(result: dict) -> str:
    """재무제표 표(연간 5년 요약 + 분기 9개 손익)를 마크다운으로 생성.

    숫자 정확성을 코드가 보증하기 위해 LLM이 아닌 여기서 직접 표를 만든다
    (출처 footer를 코드가 append하는 것과 동일한 철학). 값은 콤마 문자열로 포맷해
    전치·혼합 dtype으로 인한 지수표기(2.79e+06)를 원천 차단한다.
    """
    metrics      = result.get('metrics') or {}
    df_fin       = result.get('df_fin')
    df_quarterly = result.get('df_quarterly')

    parts = []

    # 연간 실적 추이 (최근 5년)
    if metrics and df_fin is not None and not df_fin.empty:
        years    = df_fin.index.tolist()[-5:]
        year_str = [str(y) for y in years]

        def _eok_row(series):
            return [_fmt_eok(v) for v in series.reindex(years)]

        def _pct_row(series):
            return [_fmt_pct(v) for v in series.reindex(years)]

        annual = pd.DataFrame({
            '매출액(억원)':     _eok_row(metrics['sales']),
            '영업이익(억원)':   _eok_row(metrics['op_profit']),
            '당기순이익(억원)': _eok_row(metrics['net_profit']),
            'OPM(%)':          _pct_row(metrics['opm']),
            'ROE(%)':          _pct_row(metrics['roe']),
            '부채비율(%)':      _pct_row(metrics['debt_ratio']),
        }, index=year_str).T
        # disable_numparse: tabulate가 콤마 문자열을 숫자로 재파싱해 지수표기(2.79e+06)로
        # 바꾸는 것을 방지 — 이미 포맷된 문자열을 그대로 표시
        parts.append('**연간 실적 추이 (최근 5년)**\n\n' + annual.to_markdown(disable_numparse=True))

    # 분기 손익 (최근 9개 분기, 억원) — df_quarterly는 원 단위, _fmt_eok가 억원으로 변환
    if df_quarterly is not None and not df_quarterly.empty:
        q_str = df_quarterly.map(_fmt_eok)
        parts.append('**분기 손익 (최근 9개 분기, 단위: 억원)**\n\n' + q_str.to_markdown(disable_numparse=True))

    if not parts:
        return '_재무제표 데이터를 수집하지 못했습니다._'
    return '\n\n'.join(parts)


def _build_prompt(result: dict) -> str:
    name           = result['company_name']
    stock_code     = result['stock_code']
    current_price  = result['current_price']
    market_cap     = result['market_cap']
    shares_out     = result['shares_out']
    df_quarterly   = result['df_quarterly']
    metrics        = result['metrics']
    df_fin         = result['df_fin']
    broker_reports = result.get('broker_reports') or []
    cafe_posts     = result.get('cafe_posts') or []

    per            = result.get('per')
    pbr            = result.get('pbr')
    eps            = result.get('eps')
    bps            = result.get('bps')
    foreign_ratio  = result.get('foreign_ratio')

    rim_value    = metrics.get('rim_value') if metrics else None
    rim_str      = f"{rim_value:,.0f} 원" if isinstance(rim_value, float) else "계산 불가"
    mcap_str     = f"{market_cap / 1e12:.1f}조 원" if market_cap > 0 else "수집 불가"
    shares_str   = f"{shares_out:,.0f} 주" if shares_out > 0 else "수집 불가"
    price_str    = f"{current_price:,.0f} 원"
    per_pbr_str  = f"{per:.2f} / {pbr:.2f}" if per is not None and pbr is not None else "[AI 기입]"
    eps_bps_str  = f"{eps:,.0f}원 / {bps:,.0f}원" if eps is not None and bps is not None else "[AI 기입]"
    foreign_str  = f"{foreign_ratio:.2f}%" if foreign_ratio is not None else "[AI 기입]"

    # 연간 주요 지표 요약 (df_fin 인덱스 = 연도)
    annual_summary = ""
    if metrics and not df_fin.empty:
        years = df_fin.index.tolist()[-5:]  # 최근 5년만
        lines = []
        for label, key in [('OPM(%)', 'opm'), ('ROE(%)', 'roe'), ('부채비율(%)', 'debt_ratio')]:
            vals = metrics[key][years].round(1).to_dict()
            lines.append(f"{label}: " + ", ".join(f"{k}={v}" for k, v in vals.items()))
        annual_summary = "\n".join(lines)

    # 억원 단위로 반올림 — 지수표기(7.19e+13) 대신 가독성 있는 정수로 표시
    quarterly_str = (
        (df_quarterly / 1e8).round(0).astype("Int64").to_markdown()
        if not df_quarterly.empty else "수집 불가"
    )

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

[최근 9개 분기 재무제표 (단위: 억원)]
{quarterly_str}

[기존 증권사 리포트 발췌 (최신 {len(broker_reports)}건)]
{_build_broker_excerpt_block(broker_reports)}

[카페 IR콜/탐방 메모 발췌 (최신 {len(cafe_posts)}건)]
{_build_cafe_excerpt_block(cafe_posts)}

---
[보고서 양식 - 아래 구조 그대로 작성, 섹션 누락 금지]

## 1. 사업현황

### 1) 주요지표
| 지표 | 수치 | 지표 | 수치 |
|---|---|---|---|
| **현재 주가** | {price_str} | **시가총액** | {mcap_str} |
| **대주주지분** | [AI 기입] | **외국인지분율** | {foreign_str} |
| **발행주식수** | {shares_str} | **수출비중** | [AI 기입] |
| **배당성향/수익률** | [AI 기입] | **PER / PBR** | {per_pbr_str} |
| **EPS / BPS** | {eps_bps_str} | | |

### 2) 주요사업내용
[{name}의 핵심 비즈니스 모델 및 사업부별 매출 비중을 상세히 기술]

### 3) 최근 분기 실적 및 주요 이벤트
[위 분기 데이터 기반으로 실적 모멘텀 분석. 턴어라운드/훼손 여부 판단]

### 4) 기업 지배구조 및 임직원 현황
- **최대주주 및 주요주주 지분율**: [AI 기입]
- **사내이사 현황**: [AI 기입]

### 5) 재무현황 요약
[연간 지표 기반 매출/이익/부채 트렌드 핵심 2줄 요약]

## 2. 재무제표 현황
[연간·분기 재무제표의 핵심 추세(성장성/수익성/안정성)를 2~3줄로만 해설하십시오.
표와 수치 데이터는 코드가 이 해설 바로 아래에 자동으로 삽입하므로, 귀하는 표나
구체적 숫자 나열을 절대 작성하지 말고 해설 문장만 쓰십시오.]

## 3. 주요 고객 및 경쟁사 비교
[주요 고객사 및 경쟁사 대비 포지셔닝 분석]

## 4. 경쟁우위요소 (Economic Moat)
[{name}만의 지속 가능한 경쟁 해자를 구체적으로 분석]

## 5. 투자 아이디어
[위 "기존 증권사 리포트 발췌"와 "카페 IR콜/탐방 메모 발췌"가 있다면 그 논거(수주, 신사업, 실적 모멘텀,
현장 코멘트 등)를 핵심 재료로 삼되, 귀하가 알고 있는 폭넓은 산업 지식(경쟁구도, 매크로 트렌드, 기술 변화,
밸류체인 등)을 함께 결합하여 더 입체적이고 종합적인 핵심 투자 포인트 3~4가지를 번호 목록으로 상세 기술하십시오.
단, 본문에 특정 증권사명·리포트 제목이나 카페 게시글 제목·작성자를 직접 언급하지 마십시오
(출처는 보고서 하단에 별도 첨부됨). 발췌가 없는 경우 귀하의 산업 지식만으로 작성하십시오.]

## 6. 기업가치 평가
- **RIM 내재가치**: {rim_str} (ke=8% 적용) → [현재 주가 대비 괴리율 계산 및 해석]
- **Forwarding POR**: [분기 모멘텀 반영 향후 2~3년 추정 실적 기반 산출]
- **PER/PBR 밴드 분석**: [AI 기입]

## 7. 리스크 및 모니터링
[위 "기존 증권사 리포트 발췌"와 "카페 IR콜/탐방 메모 발췌"에 언급된 우려사항(고객사 집중, 경쟁 심화,
정책 리스크 등)이 있다면 핵심 재료로 반영하되, 귀하의 산업 지식(구조적 리스크, 매크로 변수, 규제 동향 등)을
함께 결합하여 더 종합적인 리스크를 도출하십시오. 본문에 특정 증권사명·리포트 제목이나 카페 게시글
제목·작성자를 직접 언급하지 마십시오. 발췌가 없는 경우 귀하의 산업 지식만으로 작성하십시오.]
1. [리스크 1]
2. [리스크 2]
3. [리스크 3]

## 8. 결론 및 최종 투자의견
[2~3줄 강력한 요약 및 매수/중립/매도 의견과 목표주가 제시]
"""
