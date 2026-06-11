from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

# Board HTML -> PDF via a headless Chromium-based browser already installed on
# the machine (Edge ships with Windows; Chrome/Chromium covered too). Zero new
# Python dependencies — keeps the ₩0 principle.

_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser() -> str | None:
    """First Chromium-based browser found. NYLB_BROWSER env var overrides."""
    override = os.environ.get("NYLB_BROWSER")
    if override and Path(override).exists():
        return override
    for c in _CANDIDATES:
        if Path(c).exists():
            return c
    return None


def pdf_command(browser: str, html_path: Path, pdf_path: Path) -> list[str]:
    return [browser, "--headless", "--disable-gpu", "--disable-extensions",
            "--no-first-run", "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path.resolve()}",
            html_path.resolve().as_uri()]


def export_pdf(html: str, pdf_path: str | Path, *,
               browser: str | None = None, timeout: int = 120) -> Path:
    """Write `html` to a temp file and print it to `pdf_path`. Raises
    RuntimeError when no browser is available or the print produced nothing."""
    browser = browser or find_browser()
    if not browser:
        raise RuntimeError(
            "PDF 추출용 브라우저(Edge/Chrome)를 찾지 못했습니다 — "
            "NYLB_BROWSER 환경변수로 실행파일 경로를 지정하세요")
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "board.html"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run(pdf_command(browser, html_path, pdf_path),
                       check=True, capture_output=True, timeout=timeout)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError("PDF 생성 실패 — 브라우저가 빈 출력을 반환")
    return pdf_path
