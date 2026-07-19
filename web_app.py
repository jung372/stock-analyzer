import os
import pathlib
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, send_from_directory

# Windows 콘솔 기본 인코딩(cp949)에서 이모지 등 print() 실패 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

from business.analyzer   import run_analysis
from presentation.charts import generate_charts_html
from llm.claude_client   import generate_report
from data.stock_list     import load_corp_list, search_corps
from data.report_cache   import init_store, get_cached_report, save_report, list_reports
from data.naver_cafe     import has_valid_session, login_in_progress, run_login_flow
from backup_reports      import backup as backup_reports

app          = Flask(__name__)
_corps       = []
_corps_ready = False

BASE_DIR    = pathlib.Path(__file__).parent
INDEX_HTML  = BASE_DIR / 'index.html'
REPORTS_DIR = BASE_DIR / 'data' / 'reports'

# ── 비동기 생성 작업 상태 (단일 사용자라 인메모리로 충분) ──
_jobs           = {}                    # job_id -> {status, step, stock_code, error, payload, started_at}
_jobs_lock      = threading.Lock()
_active_by_code = {}                    # stock_code -> job_id (single-flight)
_gen_semaphore  = threading.Semaphore(1)  # 생성 직렬화 (KIS 레이트리밋·CPU 보호)


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


def _is_local_request() -> bool:
    """요청이 로컬 PC 자신에서 온 것인지(127.0.0.1) 여부 — 대화형 네이버 로그인 허용 판단용."""
    return request.remote_addr in ('127.0.0.1', '::1', 'localhost')


# ══ 정적 서빙 (same-origin: 폰이 Tailscale로 접속해도 동일 출처) ══
@app.route('/')
def index():
    return Response(INDEX_HTML.read_text(encoding='utf-8'), mimetype='text/html')


@app.route('/reports/<path:filename>')
def reports_static(filename):
    """생성된 보고서 JSON·차트 HTML·index.json 정적 서빙."""
    return send_from_directory(REPORTS_DIR, filename)


@app.route('/status')
def status():
    return jsonify({'ready': _corps_ready, 'count': len(_corps)})


@app.route('/stocks')
def stocks():
    q = request.args.get('q', '').strip()
    return jsonify(search_corps(_corps, q))


@app.route('/reports-list')
def reports_list():
    """이미 생성된 보고서 목록 (열람 모드 자동완성/목록용)."""
    return jsonify(list_reports())


@app.route('/naver-cafe/status')
def naver_cafe_status():
    """네이버 카페 로그인 여부 확인 (프론트엔드 게이트/폴링용)."""
    return jsonify({'logged_in': has_valid_session(), 'in_progress': login_in_progress()})


@app.route('/naver-cafe/login', methods=['POST'])
def naver_cafe_login():
    """대화형 네이버 로그인은 PC에 브라우저 창을 띄우므로 로컬(PC) 요청만 허용.
    모바일/원격 요청은 403 — 프론트엔드는 대신 '카페 없이 생성' 안내를 표시한다."""
    if not _is_local_request():
        return jsonify({'started': False, 'error': 'PC(로컬)에서만 네이버 카페 로그인이 가능합니다.'}), 403
    if login_in_progress():
        return jsonify({'started': False, 'already_running': True})
    threading.Thread(target=run_login_flow, kwargs={'headless': False}, daemon=True).start()
    return jsonify({'started': True})


def _run_job(job_id: str, company_name: str, stock_code: str, corp_code: str):
    """백그라운드 워커 — 실제 생성(수집→차트→AI)을 수행하고 파일 저장소에 기록."""
    def set_step(step: str):
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]['step'] = step

    with _gen_semaphore:  # 한 번에 하나의 생성만 (대기 job은 여기서 큐잉)
        try:
            set_step('데이터 수집 중 (KIS·Drive·카페)...')
            result = run_analysis(company_name, stock_code)

            set_step('차트 생성 중...')
            charts_html = generate_charts_html(result)

            set_step('Claude AI 보고서 생성 중...')
            report_md = generate_report(result)

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
            payload['generated_at'] = datetime.now(timezone.utc).isoformat()
            payload['from_cache']   = False

            try:
                backup_reports()
            except Exception as e:
                print(f'[WARN] 백업 실패: {e}')

            with _jobs_lock:
                _jobs[job_id].update(status='done', step='완료', payload=payload)

        except Exception as e:
            print(f'[ERROR] 생성 실패 ({stock_code}): {e}')
            with _jobs_lock:
                _jobs[job_id].update(status='error', error=f'분석 중 오류 발생: {e}')
        finally:
            with _jobs_lock:
                if _active_by_code.get(stock_code) == job_id:
                    del _active_by_code[stock_code]


@app.route('/analyze', methods=['POST'])
def analyze():
    """생성 트리거 — 즉시 job_id를 반환하고 실제 생성은 백그라운드 워커가 수행.
    cache-first: 기존 보고서가 있으면(force_refresh 아니면) 재생성 없이 바로 반환."""
    body          = request.get_json(force=True)
    company_name  = body.get('company_name', '').strip()
    stock_code    = body.get('stock_code',   '').strip()
    corp_code     = body.get('corp_code',    '').strip()
    force_refresh = bool(body.get('force_refresh', False))

    if not all([company_name, stock_code, corp_code]):
        return jsonify({'error': '종목 정보가 올바르지 않습니다.'}), 400

    # cache-first — 업데이트(force_refresh) 전까지 신규 생성하지 않음
    if not force_refresh:
        cached = get_cached_report(stock_code)
        if cached is not None:
            print(f'[CACHE HIT] {stock_code} - 저장된 보고서 반환')
            cached['from_cache'] = True
            return jsonify({'status': 'done', 'from_cache': True, 'payload': cached})

    # single-flight — 같은 종목 생성이 진행 중이면 그 job을 재사용
    with _jobs_lock:
        existing = _active_by_code.get(stock_code)
        if existing and _jobs.get(existing, {}).get('status') == 'running':
            return jsonify({'status': 'running', 'job_id': existing})

        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            'status':     'running',
            'step':       '대기 중...',
            'stock_code': stock_code,
            'error':      None,
            'payload':    None,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        _active_by_code[stock_code] = job_id

    threading.Thread(
        target=_run_job, args=(job_id, company_name, stock_code, corp_code), daemon=True
    ).start()
    return jsonify({'status': 'running', 'job_id': job_id})


@app.route('/analyze/status/<job_id>')
def analyze_status(job_id):
    """폴링 엔드포인트 — running/done/error 상태와 진행 단계를 반환."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({'status': 'unknown'}), 404
        resp = {'status': job['status'], 'step': job['step']}
        if job['status'] == 'done':
            resp['payload'] = job['payload']
        elif job['status'] == 'error':
            resp['error'] = job['error']
    return jsonify(resp)


if __name__ == '__main__':
    init_store()
    threading.Thread(target=_init_corps, daemon=True).start()
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5000/')).start()
    # host='0.0.0.0' — Tailscale 인터페이스에서 폰이 접근 가능하게 노출
    app.run(host='0.0.0.0', debug=False, port=5000)
