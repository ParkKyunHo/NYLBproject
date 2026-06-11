from pathlib import Path

import pytest

import nylb.report.pdf as pdf


def test_find_browser_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "browser.exe"
    fake.write_text("x")
    monkeypatch.setenv("NYLB_BROWSER", str(fake))
    assert pdf.find_browser() == str(fake)


def test_find_browser_none_when_nothing_exists(monkeypatch):
    monkeypatch.delenv("NYLB_BROWSER", raising=False)
    monkeypatch.setattr(pdf, "_CANDIDATES", ["/nope/a", "/nope/b"])
    assert pdf.find_browser() is None


def test_pdf_command_shape(tmp_path):
    cmd = pdf.pdf_command("browser.exe", tmp_path / "in.html", tmp_path / "out.pdf")
    assert cmd[0] == "browser.exe"
    assert "--headless" in cmd and "--no-pdf-header-footer" in cmd
    assert any(a.startswith("--print-to-pdf=") for a in cmd)
    assert cmd[-1].startswith("file://")          # html passed as file URI


def test_export_pdf_raises_without_browser(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf, "find_browser", lambda: None)
    with pytest.raises(RuntimeError, match="브라우저"):
        pdf.export_pdf("<html></html>", tmp_path / "o.pdf")


def test_export_pdf_runs_browser_and_returns_path(monkeypatch, tmp_path):
    def fake_run(cmd, check, capture_output, timeout):
        target = next(a for a in cmd if a.startswith("--print-to-pdf="))
        Path(target.split("=", 1)[1]).write_bytes(b"%PDF-1.7 fake")
    monkeypatch.setattr(pdf.subprocess, "run", fake_run)
    out = pdf.export_pdf("<html></html>", tmp_path / "o.pdf", browser="fake.exe")
    assert out.read_bytes().startswith(b"%PDF")


def test_export_pdf_raises_on_empty_output(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf.subprocess, "run",
                        lambda *a, **k: None)     # browser "succeeds" but writes nothing
    with pytest.raises(RuntimeError, match="생성 실패"):
        pdf.export_pdf("<html></html>", tmp_path / "o.pdf", browser="fake.exe")
