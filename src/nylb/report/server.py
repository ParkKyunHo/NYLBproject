from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


def run_lenses_and_render(lens_keys: list[str], *, lenses_file: str = "config/lenses.yaml",
                          store_id: str = "nylb", collectors=None) -> str:
    from nylb.config import load_settings
    from nylb.report.multi import build_lenses_dashboard
    return build_lenses_dashboard(lens_keys, lenses_file=lenses_file, store_id=store_id,
                                  settings=load_settings(), collectors=collectors)


def make_server(host: str = "127.0.0.1", port: int = 8765, *,
                lens: str = "menu", lens_keys=None, lenses_file: str = "config/lenses.yaml",
                render_fn=None, **_) -> ThreadingHTTPServer:
    keys = lens_keys or [lens]
    render = render_fn or (lambda: run_lenses_and_render(keys, lenses_file=lenses_file))
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
