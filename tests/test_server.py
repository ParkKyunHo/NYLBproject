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
    server.shutdown()
    assert "스캔 실행" in body          # button injected
    assert "fetch('/run'" in body


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
