import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def draw_charts(result: dict) -> None:
    """
    3단 matplotlib 차트 렌더링

    BUG FIX:
      - 'import matplotlib.pyplot as plt' 누락 수정
      - t.pause(2) → plt.pause(2) 수정
      - 빈 DataFrame 접근 시 오류 방지 (axes.text 폴백)
      - 매출액/자본 단위 억원으로 환산하여 y축 가독성 개선
    """
    matplotlib.rcParams['font.family']       = 'Malgun Gothic'
    matplotlib.rcParams['axes.unicode_minus'] = False

    df_price = result['df_price']
    metrics  = result['metrics']
    df_fin   = result['df_fin']
    name     = result['company_name']

    fig, axes = plt.subplots(3, 1, figsize=(12, 15))
    fig.suptitle(f"{name} 가치투자 분석", fontsize=16, fontweight='bold')

    # ── Chart 1: 10년 주가 추이
    if not df_price.empty:
        axes[0].plot(df_price.index, df_price['Close'],
                     color='#1f77b4', linewidth=1.5)
        axes[0].yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f'{x:,.0f}')
        )
    else:
        axes[0].text(0.5, 0.5, '주가 데이터 없음',
                     ha='center', va='center', transform=axes[0].transAxes)
    axes[0].set_title("10년 주가 추이", fontweight='bold')
    axes[0].grid(True, linestyle='--', alpha=0.6)

    # ── Chart 2: 수익성 트렌드 (Sales Bar / OPM·ROE Line, 이중축)
    if metrics and not df_fin.empty:
        ax2t = axes[1].twinx()
        axes[1].bar(df_fin.columns, metrics['sales'] / 1e8,
                    color='#e1e1e1', alpha=0.7, label='매출액(억원)')
        ax2t.plot(df_fin.columns, metrics['opm'],
                  color='blue',  marker='o', linewidth=1.5, label='OPM (%)')
        ax2t.plot(df_fin.columns, metrics['roe'],
                  color='red',   marker='s', linewidth=1.5, label='ROE (%)')
        axes[1].legend(loc='upper left')
        ax2t.legend(loc='upper right')
    else:
        axes[1].text(0.5, 0.5, '재무 데이터 없음',
                     ha='center', va='center', transform=axes[1].transAxes)
    axes[1].set_title("수익성 트렌드 (매출액 / OPM / ROE)", fontweight='bold')

    # ── Chart 3: 자본구조 (Equity Bar / 부채비율 Line, 이중축)
    if metrics and not df_fin.empty:
        ax3t = axes[2].twinx()
        axes[2].bar(df_fin.columns, metrics['equity'] / 1e8,
                    color='#d6ffd6', alpha=0.7, label='자본총계(억원)')
        ax3t.plot(df_fin.columns, metrics['debt_ratio'],
                  color='purple', marker='^', linewidth=1.5, label='부채비율 (%)')
        axes[2].legend(loc='upper left')
        ax3t.legend(loc='upper right')
    else:
        axes[2].text(0.5, 0.5, '재무 데이터 없음',
                     ha='center', va='center', transform=axes[2].transAxes)
    axes[2].set_title("자본구조 (자본총계 / 부채비율)", fontweight='bold')

    plt.tight_layout()
    plt.show(block=False)
    plt.pause(2)


def generate_plotly_html(result: dict, full_html: bool = False) -> str:
    """Plotly 3단 인터랙티브 차트 반환.

    full_html=False (기본): 임베드용 div 문자열
    full_html=True: iframe 삽입용 완전한 HTML 문서
    """
    df_price = result['df_price']
    metrics  = result['metrics']
    df_fin   = result['df_fin']
    name     = result['company_name']

    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=("10년 주가 추이", "수익성 트렌드 (OPM / ROE)", "자본구조 (부채비율)"),
        vertical_spacing=0.1,
        specs=[[{"secondary_y": False}],
               [{"secondary_y": True}],
               [{"secondary_y": True}]],
    )

    # Chart 1: 주가 추이
    if not df_price.empty:
        fig.add_trace(go.Scatter(
            x=df_price.index, y=df_price['Close'],
            mode='lines', name='종가',
            line=dict(color='#3b82f6', width=1.5)
        ), row=1, col=1)

    # Chart 2: 수익성
    if metrics and not df_fin.empty:
        cols = list(df_fin.columns)
        fig.add_trace(go.Bar(
            x=cols, y=metrics['sales'] / 1e8,
            name='매출액(억원)', marker_color='#e2e8f0', opacity=0.8
        ), row=2, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['opm'],
            mode='lines+markers', name='OPM(%)',
            line=dict(color='#3b82f6', width=2), marker=dict(size=5)
        ), row=2, col=1, secondary_y=True)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['roe'],
            mode='lines+markers', name='ROE(%)',
            line=dict(color='#ef4444', width=2), marker=dict(size=5)
        ), row=2, col=1, secondary_y=True)

    # Chart 3: 자본구조
    if metrics and not df_fin.empty:
        cols = list(df_fin.columns)
        fig.add_trace(go.Bar(
            x=cols, y=metrics['equity'] / 1e8,
            name='자본총계(억원)', marker_color='#bbf7d0', opacity=0.8
        ), row=3, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=cols, y=metrics['debt_ratio'],
            mode='lines+markers', name='부채비율(%)',
            line=dict(color='#a855f7', width=2), marker=dict(size=5)
        ), row=3, col=1, secondary_y=True)

    fig.update_layout(
        title=dict(text=f"{name} 재무 분석 차트", font=dict(size=16)),
        height=900,
        template='plotly_white',
        legend=dict(orientation='h', y=-0.05),
        margin=dict(t=60, b=60),
    )
    return fig.to_html(full_html=full_html, include_plotlyjs='cdn')
