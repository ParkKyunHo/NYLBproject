from __future__ import annotations

from pathlib import Path


def write_text_report(content: str, run_id: str, *,
                      out_dir: Path | str = "reports", suffix: str = ".md") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_id}{suffix}"
    path.write_text(content, encoding="utf-8")
    return path
