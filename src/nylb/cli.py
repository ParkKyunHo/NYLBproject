from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from nylb.config import get_lens_config, load_lenses, load_settings
from nylb.core.analyzer import ClaudeCodeAnalyzer
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
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
    args = parser.parse_args(argv)

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
