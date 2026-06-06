from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nylb.config import get_lens_config, load_lenses, load_settings
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_dashboard

_BUTTON = (
    "<div style=\"position:fixed;right:20px;bottom:20px;z-index:9999\">"
    "<button id=\"nylb-run\" style=\"background:#c8742f;color:#fff;border:0;"
    "border-radius:999px;padding:13px 22px;font-size:15px;font-weight:800;"
    "box-shadow:0 6px 20px rgba(45,38,32,.3);cursor:pointer\">🔄 스캔 실행</button></div>"
    "<script>document.getElementById('nylb-run').onclick=function(){"
    "this.textContent='⏳ 수집 중...';this.disabled=true;"
    "fetch('/run',{method:'POST'}).then(function(){location.reload();}).catch(function(){location.reload();});};</script>"
)
_PLACEHOLDER = ("<!DOCTYPE html><html lang=ko><body style=\"font-family:sans-serif;"
                "padding:40px\"><h2>NYLB 의사결정 상황판</h2>"
                "<p>아직 스캔이 없습니다. 오른쪽 아래 <b>스캔 실행</b> 버튼을 누르세요.</p>"
                "</body></html>")


def _with_button(html: str) -> str:
    if "</body>" in html:
        return html.replace("</body>", _BUTTON + "</body>", 1)
    return html + _BUTTON


def run_scan_and_render(lens: str = "menu", *, lenses_file: str = "config/lenses.yaml",
                        store_id: str = "nylb", collectors=None) -> str:
    """Run a local scan and return the rendered board HTML (no synthesis, no LLM)."""
    from nylb.cli import build_run_id  # deferred import: cli imports nylb.report.*, avoid circular import
    now = datetime.now(timezone.utc)
    settings = load_settings()
    lenses = load_lenses(lenses_file)
    lens_config = get_lens_config(lenses, store_id, lens)
    run_id = build_run_id(lens, now)
    result = run_scan(lens, store_id=store_id, lens_config=lens_config,
                      settings=settings, store=LocalJsonStore(), run_id=run_id,
                      collected_at=now, collectors=collectors)
    chart = extract_chart_data(result)
    from nylb.report.news import gather_riser_news
    news = gather_riser_news(result, chart, settings)
    return build_dashboard(result, chart, news_context=news)


def make_server(host: str = "127.0.0.1", port: int = 8765, *,
                lens: str = "menu", lenses_file: str = "config/lenses.yaml",
                render_fn=None, **_) -> ThreadingHTTPServer:
    render = render_fn or (lambda: run_scan_and_render(lens, lenses_file=lenses_file))
    # single shared board HTML; GIL makes dict get/set atomic — fine for single-user local use
    state = {"html": _PLACEHOLDER}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/board"):
                self._send(200, _with_button(state["html"]))
            else:
                self._send(404, "not found")

        def do_POST(self):
            if self.path == "/run":
                state["html"] = render()
                self._send(200, _with_button(state["html"]))
            else:
                self._send(404, "not found")

        def log_message(self, *a):  # silence default stderr logging
            pass

    return ThreadingHTTPServer((host, port), Handler)
