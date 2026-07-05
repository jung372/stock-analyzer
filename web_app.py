import os
import pathlib
import threading
import webbrowser
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

from business.analyzer   import run_analysis
from presentation.charts import generate_plotly_html
from llm.claude_client   import generate_report
from data.stock_list     import load_corp_list, search_corps
from data.report_cache   import init_db, get_cached_report, save_report
from backup_reports      import backup as backup_reports

app          = Flask(__name__)
_corps       = []
_corps_ready = False


def _init_corps():
    global _corps, _corps_ready
    api_key = os.getenv('DART_API_KEY', '')
    if not api_key:
        print('[WARN] DART_API_KEY 없음 - 종목 자동완성 비활성화')
    else:
        try:
            _corps = load_corp_list(api_key)
            print(f'[INFO] 기업 목록 로드 완료: {len(_corps)}개')
        except Exception as e:
            print(f'[WARN] 기업 목록 로드 실패: {e}')
    _corps_ready = True


@app.after_request
def _cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


@app.route('/status')
def status():
    return jsonify({'ready': _corps_ready, 'count': len(_corps)})


@app.route('/stocks')
def stocks():
    q = request.args.get('q', '').strip()
    return jsonify(search_corps(_corps, q))


@app.route('/analyze', methods=['POST', 'OPTIONS'])
def analyze():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    body          = request.get_json(force=True)
    company_name  = body.get('company_name', '').strip()
    stock_code    = body.get('stock_code',   '').strip()
    corp_code     = body.get('corp_code',    '').strip()
    force_refresh = bool(body.get('force_refresh', False))

    if not all([company_name, stock_code, corp_code]):
        return jsonify({'error': '종목 정보가 올바르지 않습니다.'}), 400

    if not force_refresh:
        cached = get_cached_report(stock_code)
        if cached is not None:
            print(f'[CACHE HIT] {stock_code} - 캐시된 리포트 반환')
            return jsonify(cached)

    try:
        result      = run_analysis(company_name, stock_code, corp_code)
        charts_html = generate_plotly_html(result, full_html=True)
        report_md   = generate_report(result)

        metrics   = result.get('metrics') or {}
        rim_value = metrics.get('rim_value')
        rim_str   = f"{rim_value:,.0f} 원" if isinstance(rim_value, (int, float)) else "데이터 부족"

        payload = {
            'company_name':  result['company_name'],
            'stock_code':    result['stock_code'],
            'current_price': result['current_price'],
            'market_cap':    result['market_cap'],
            'shares_out':    result['shares_out'],
            'rim_str':       rim_str,
            'charts_html':   charts_html,
            'report_md':     report_md,
        }
        save_report(stock_code, corp_code, payload)

        try:
            backup_reports()
        except Exception as e:
            print(f'[WARN] 백업 실패: {e}')

        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': f'분석 중 오류 발생: {e}'}), 500


if __name__ == '__main__':
    init_db()
    threading.Thread(target=_init_corps, daemon=True).start()
    index_path = pathlib.Path(__file__).parent / 'index.html'
    threading.Timer(1.0, lambda: webbrowser.open(index_path.as_uri())).start()
    app.run(debug=False, port=5000)
