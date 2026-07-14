import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 한국식 캔들 색상: 상승 빨강 / 하락 파랑
_UP_COLOR   = '#ef4444'
_DOWN_COLOR = '#2563eb'


def generate_price_chart_html(result: dict, include_plotlyjs='cdn') -> str:
    """TradingView 스타일 캔들차트 (캔들 + 거래량 + 기간선택 버튼).

    KRX 종목은 TradingView 무료 임베드 위젯이 라이선스상 지원하지 않으므로,
    이미 수집한 FinanceDataReader OHLCV 데이터로 직접 인터랙티브 차트를 그림.
    """
    df_price = result['df_price']
    name     = result['company_name']

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.74, 0.26], vertical_spacing=0.04,
        subplot_titles=("10년 주가 추이", "거래량"),
    )

    if not df_price.empty:
        fig.add_trace(go.Candlestick(
            x=df_price.index,
            open=df_price['Open'],  high=df_price['High'],
            low=df_price['Low'],    close=df_price['Close'],
            name='주가',
            increasing=dict(line=dict(color=_UP_COLOR),   fillcolor=_UP_COLOR),
            decreasing=dict(line=dict(color=_DOWN_COLOR), fillcolor=_DOWN_COLOR),
        ), row=1, col=1)

        vol_colors = [
            _UP_COLOR if c >= o else _DOWN_COLOR
            for o, c in zip(df_price['Open'], df_price['Close'])
        ]
        fig.add_trace(go.Bar(
            x=df_price.index, y=df_price['Volume'],
            marker_color=vol_colors, opacity=0.45, name='거래량',
        ), row=2, col=1)
    else:
        fig.add_annotation(text="주가 데이터 없음", showarrow=False,
                           xref="paper", yref="paper", x=0.5, y=0.5)

    fig.update_layout(
        title=dict(text=f"{name} 주가 차트", font=dict(size=16), y=0.98),
        height=560,
        template='plotly_white',
        showlegend=False,
        margin=dict(t=95, b=30, l=10, r=10),
        xaxis_rangeslider_visible=False,   # 캔들 기본 슬라이더 제거
    )
    # 기간 선택 버튼 (TradingView 스타일)
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label='1개월', step='month', stepmode='backward'),
                dict(count=6, label='6개월', step='month', stepmode='backward'),
                dict(count=1, label='1년',  step='year',  stepmode='backward'),
                dict(count=3, label='3년',  step='year',  stepmode='backward'),
                dict(count=5, label='5년',  step='year',  stepmode='backward'),
                dict(step='all', label='전체'),
            ],
            x=0, y=1.02, xanchor='left', yanchor='bottom',
            bgcolor='#f1f5f9', activecolor='#3b82f6',
            font=dict(size=11),
        ),
        row=1, col=1,
    )
    return fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)


def generate_plotly_html(result: dict, include_plotlyjs=False) -> str:
    """재무 분석 2단 차트 (수익성 트렌드 · 자본구조) div 문자열 반환."""
    metrics = result['metrics']
    df_fin  = result['df_fin']

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("수익성 트렌드 (OPM / ROE)", "자본구조 (부채비율)"),
        vertical_spacing=0.12,
        specs=[[{"secondary_y": True}],
               [{"secondary_y": True}]],
    )

    # Chart 1: 수익성
    if metrics and not df_fin.empty:
        cols = list(df_fin.index)
        fig.add_trace(go.Bar(
            x=cols, y=metrics['sales'] / 1e8,
            name='매출액(억원)', marker_color='#e2e8f0', opacity=0.8
        ), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['opm'],
            mode='lines+markers', name='OPM(%)',
            line=dict(color='#3b82f6', width=2), marker=dict(size=5)
        ), row=1, col=1, secondary_y=True)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['roe'],
            mode='lines+markers', name='ROE(%)',
            line=dict(color='#ef4444', width=2), marker=dict(size=5)
        ), row=1, col=1, secondary_y=True)

    # Chart 2: 자본구조
    if metrics and not df_fin.empty:
        cols = list(df_fin.index)
        fig.add_trace(go.Bar(
            x=cols, y=metrics['equity'] / 1e8,
            name='자본총계(억원)', marker_color='#bbf7d0', opacity=0.8
        ), row=2, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['debt_ratio'],
            mode='lines+markers', name='부채비율(%)',
            line=dict(color='#a855f7', width=2), marker=dict(size=5)
        ), row=2, col=1, secondary_y=True)

    fig.update_layout(
        title=dict(text="재무 분석 차트", font=dict(size=16)),
        height=650,
        template='plotly_white',
        legend=dict(orientation='h', y=-0.08),
        margin=dict(t=60, b=60),
    )
    return fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)


def generate_charts_html(result: dict) -> str:
    """주가 캔들차트(상단) + 재무 분석 차트(하단)를 하나의 완전한 HTML 문서로 결합.

    plotly.js는 첫 차트에서 CDN으로 1회만 로드하고, 두 번째는 재사용(include_plotlyjs=False).
    iframe 삽입 및 report_cache 저장용."""
    price_html = generate_price_chart_html(result, include_plotlyjs='cdn')
    fin_html   = generate_plotly_html(result, include_plotlyjs=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8" /></head>
<body style="margin:0;">
{price_html}
{fin_html}
</body>
</html>"""
