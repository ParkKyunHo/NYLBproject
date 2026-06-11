from __future__ import annotations

import tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nylb.report.pdf import export_pdf

_BTN_GHOST = ("background:#fffdf6;color:#241b10;border:1px solid #d6c9ad;"
              "border-radius:999px;padding:14px 20px;font-size:13px;font-weight:800;"
              "letter-spacing:.04em;text-decoration:none;font-family:inherit;"
              "box-shadow:0 10px 26px -12px rgba(32,23,16,.4);cursor:pointer")
_BUTTON = (
    "<div id=\"nylb-actions\" style=\"position:fixed;right:22px;bottom:22px;"
    "z-index:9999;display:flex;gap:10px;align-items:center\">"
    "<form action=\"/validate\" method=\"get\" target=\"_blank\" style=\"margin:0\">"
    "<input name=\"term\" placeholder=\"🔬 후보 검증 (예: 복숭아 크림치즈)\" required"
    " style=\"background:#fffdf6;color:#241b10;border:1px solid #d6c9ad;"
    "border-radius:999px;padding:14px 18px;font-size:13px;font-family:inherit;"
    "width:230px;box-shadow:0 10px 26px -12px rgba(32,23,16,.4)\"></form>"
    f"<a id=\"nylb-pdf\" href=\"/pdf\" style=\"{_BTN_GHOST}\">⬇ PDF</a>"
    f"<a id=\"nylb-html\" href=\"/download\" style=\"{_BTN_GHOST}\">⬇ HTML</a>"
    "<button id=\"nylb-run\" style=\"background:#201710;color:#f3e8d2;"
    "border:1px solid #a8772a;border-radius:999px;padding:14px 26px;"
    "font-size:14px;font-weight:800;letter-spacing:.06em;font-family:inherit;"
    "box-shadow:0 14px 34px -10px rgba(32,23,16,.55);cursor:pointer\""
    " onmouseover=\"this.style.background='#2e2417'\""
    " onmouseout=\"this.style.background='#201710'\">◉ 스캔 실행</button></div>"
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


def _default_validate(term: str, lens: str, lenses_file: str) -> str:
    from nylb.config import load_settings
    from nylb.report.validate import run_validation
    return run_validation(term, lens=lens, lenses_file=lenses_file,
                          settings=load_settings())


def make_server(host: str = "127.0.0.1", port: int = 8765, *,
                lens: str = "menu", lens_keys=None, lenses_file: str = "config/lenses.yaml",
                render_fn=None, validate_fn=None, **_) -> ThreadingHTTPServer:
    keys = lens_keys or [lens]
    render = render_fn or (lambda: run_lenses_and_render(keys, lenses_file=lenses_file))
    validate = validate_fn or (lambda term: _default_validate(term, keys[0], lenses_file))
    # single shared board HTML; GIL makes dict get/set atomic — fine for single-user local use
    state = {"html": _PLACEHOLDER}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str) -> None:
            self._send_bytes(code, body.encode("utf-8"), "text/html; charset=utf-8")

        def _send_bytes(self, code: int, data: bytes, ctype: str,
                        filename: str | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            if filename:  # ASCII-only filenames — no RFC 5987 escaping needed
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            stamp = f"{date.today():%Y%m%d}"
            if self.path in ("/", "/board"):
                self._send(200, _with_button(state["html"]))
            elif self.path == "/download":
                self._send_bytes(200, state["html"].encode("utf-8"),
                                 "text/html; charset=utf-8",
                                 f"nylb-board-{stamp}.html")
            elif self.path.startswith("/validate"):
                from urllib.parse import parse_qs, urlparse
                term = (parse_qs(urlparse(self.path).query).get("term") or [""])[0].strip()
                if not term:
                    self._send(400, "term 파라미터가 필요합니다 (예: /validate?term=복숭아 크림치즈)")
                    return
                try:
                    self._send(200, validate(term))
                except Exception as exc:
                    self._send(500, f"검증 실패: {exc}")
            elif self.path == "/pdf":
                try:
                    with tempfile.TemporaryDirectory() as td:
                        out = export_pdf(state["html"], Path(td) / "board.pdf")
                        data = out.read_bytes()
                except Exception as exc:
                    self._send(500, f"PDF 생성 실패: {exc}")
                    return
                self._send_bytes(200, data, "application/pdf",
                                 f"nylb-board-{stamp}.pdf")
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
