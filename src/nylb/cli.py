from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from nylb.config import get_lens_config, load_lenses, load_settings
from nylb.core.analyzer import ClaudeCodeAnalyzer
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_dashboard
from nylb.report.writer import write_text_report


def build_run_id(lens: str, now: datetime) -> str:
    return f"{now:%Y-%m-%d}-{lens}-{uuid.uuid4().hex[:6]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nylb")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_p = sub.add_parser("scan", help="collect trend data for a lens")
    scan_p.add_argument("--lens", required=True)
    scan_p.add_argument("--store", default="nylb")
    scan_p.add_argument("--lenses-file", default="config/lenses.yaml")
    rh_p = sub.add_parser("report-html", help="render the analysis HTML dashboard")
    rh_p.add_argument("--run", required=True)
    rh_p.add_argument("--store", default="nylb")
    rh_p.add_argument("--synthesis", default=None,
                      help="path to synthesis JSON (default data/raw/<run>.synthesis.json)")
    args = parser.parse_args(argv)

    if args.cmd == "report-html":
        return _report_html(args)

    if args.cmd != "scan":
        return 1

    now = datetime.now(timezone.utc)
    settings = load_settings()
    lenses = load_lenses(args.lenses_file)
    lens_config = get_lens_config(lenses, args.store, args.lens)
    run_id = build_run_id(args.lens, now)

    result = run_scan(
        args.lens, store_id=args.store, lens_config=lens_config, settings=settings,
        store=LocalJsonStore(), run_id=run_id, collected_at=now,
    )
    digest = ClaudeCodeAnalyzer().prepare(result)
    digest_path = write_text_report(digest, run_id, out_dir="data/raw", suffix=".digest.md")

    print(f"run_id={run_id}")
    print(f"items={len(result.items)} errors={len(result.errors)}")
    print(f"data=data/raw/{run_id}.json")
    print(f"digest={digest_path}")
    return 0


def _report_html(args) -> int:
    syn_path = args.synthesis or f"data/raw/{args.run}.synthesis.json"
    result = LocalJsonStore().load(args.run)
    synthesis = json.loads(Path(syn_path).read_text(encoding="utf-8"))
    chart = extract_chart_data(result)
    html = build_dashboard(result, synthesis, chart)
    path = write_text_report(html, args.run, out_dir="reports", suffix=".analysis.html")
    print(f"html={path}")
    return 0
