import threading
import urllib.request

from nylb.report.server import make_server


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def test_get_serves_board_with_run_button():
    server = make_server(port=0, render_fn=lambda: "<html><body>BOARD</body></html>")
    _serve(server)
    host, port = server.server_address
    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
    body2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/board").read().decode("utf-8")
    assert "스캔 실행" in body2
    server.shutdown()
    assert "스캔 실행" in body          # button injected
    assert "fetch('/run'" in body


def test_download_serves_html_attachment():
    server = make_server(port=0, render_fn=lambda: "x")
    _serve(server)
    host, port = server.server_address
    res = urllib.request.urlopen(f"http://127.0.0.1:{port}/download")
    body = res.read().decode("utf-8")
    dispo = res.headers.get("Content-Disposition", "")
    server.shutdown()
    assert "attachment" in dispo and dispo.endswith('.html"')
    assert "nylb-run" not in body          # raw board, no injected action buttons


def test_pdf_route_exports_current_board(monkeypatch):
    import nylb.report.server as srv

    def fake_export(html, path, **kw):
        from pathlib import Path
        p = Path(path)
        p.write_bytes(b"%PDF-1.7 " + html[:10].encode())
        return p
    monkeypatch.setattr(srv, "export_pdf", fake_export)
    server = make_server(port=0, render_fn=lambda: "x")
    _serve(server)
    host, port = server.server_address
    res = urllib.request.urlopen(f"http://127.0.0.1:{port}/pdf")
    data = res.read()
    ctype = res.headers.get("Content-Type")
    server.shutdown()
    assert data.startswith(b"%PDF") and ctype == "application/pdf"


def test_pdf_route_500_when_no_browser(monkeypatch):
    import nylb.report.server as srv

    def boom(html, path, **kw):
        raise RuntimeError("no browser")
    monkeypatch.setattr(srv, "export_pdf", boom)
    server = make_server(port=0, render_fn=lambda: "x")
    _serve(server)
    host, port = server.server_address
    import urllib.error
    with_status = None
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/pdf")
    except urllib.error.HTTPError as e:
        with_status = e.code
    server.shutdown()
    assert with_status == 500


def test_post_run_invokes_render_fn():
    state = {"n": 0}
    def render():
        state["n"] += 1
        return f"<html><body>RUN {state['n']}</body></html>"
    server = make_server(port=0, render_fn=render)
    _serve(server)
    host, port = server.server_address
    req = urllib.request.Request(f"http://127.0.0.1:{port}/run", method="POST")
    body = urllib.request.urlopen(req).read().decode("utf-8")
    server.shutdown()
    assert "RUN 1" in body
    assert state["n"] == 1
