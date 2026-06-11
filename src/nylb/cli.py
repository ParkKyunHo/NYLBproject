from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from nylb.config import get_lens_config, load_lenses, load_settings
from nylb.core.analyzer import ClaudeCodeAnalyzer
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore, SupabaseStore
from nylb.report.writer import write_text_report


def build_run_id(lens: str, now: datetime) -> str:
    return f"{now:%Y-%m-%d}-{lens}-{uuid.uuid4().hex[:6]}"


def _make_store(backend: str, store_key: str, settings: dict):
    if backend == "supabase":
        return SupabaseStore(url=settings.get("supabase_url"),
                             service_key=settings.get("supabase_service_key"),
                             store_key=store_key)
    return LocalJsonStore()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nylb")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_p = sub.add_parser("scan", help="collect trend data for a lens")
    scan_p.add_argument("--lens", required=True)
    scan_p.add_argument("--store", default="nylb")
    scan_p.add_argument("--lenses-file", default="config/lenses.yaml")
    scan_p.add_argument("--store-backend", choices=["local", "supabase"], default="local")
    rh_p = sub.add_parser("report-html", help="render the analysis HTML dashboard")
    rh_p.add_argument("--run", required=True)
    rh_p.add_argument("--store", default="nylb")
    rp_p = sub.add_parser("report-pdf", help="render the dashboard and export it as PDF")
    rp_p.add_argument("--run", required=True)
    rp_p.add_argument("--out", default=None,
                      help="output path (default reports/<run>.analysis.pdf)")
    dash_p = sub.add_parser("dashboard", help="local one-click board server")
    dash_p.add_argument("--lenses", default="menu,beverage",
                        help="comma-separated lenses to show as tabs")
    dash_p.add_argument("--lenses-file", default="config/lenses.yaml")
    dash_p.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "report-html":
        return _report_html(args)
    if args.cmd == "report-pdf":
        return _report_pdf(args)
    if args.cmd == "dashboard":
        return _dashboard(args)

    if args.cmd != "scan":
        return 1

    now = datetime.now(timezone.utc)
    settings = load_settings()
    lenses = load_lenses(args.lenses_file)
    lens_config = get_lens_config(lenses, args.store, args.lens)
    run_id = build_run_id(args.lens, now)

    store = _make_store(args.store_backend, args.store, settings)
    result = run_scan(
        args.lens, store_id=args.store, lens_config=lens_config, settings=settings,
        store=store, run_id=run_id, collected_at=now,
    )
    digest = ClaudeCodeAnalyzer().prepare(result)
    digest_path = write_text_report(digest, run_id, out_dir="data/raw", suffix=".digest.md")

    print(f"run_id={run_id}")
    print(f"items={len(result.items)} errors={len(result.errors)}")
    print(f"data=data/raw/{run_id}.json")
    print(f"digest={digest_path}")
    return 0


def _single_dashboard_html(run_id: str) -> str:
    from nylb.config import load_settings
    from nylb.report.html import build_multi_dashboard
    from nylb.report.multi import build_board_full
    result = LocalJsonStore().load(run_id)
    board = build_board_full(result, settings=load_settings())
    return build_multi_dashboard([{"key": result.lens, "label": result.lens,
                                   "icon": "🍽", "board": board}])


def _report_html(args) -> int:
    html = _single_dashboard_html(args.run)
    path = write_text_report(html, args.run, out_dir="reports", suffix=".analysis.html")
    print(f"html={path}")
    return 0


def _report_pdf(args) -> int:
    from nylb.report.pdf import export_pdf
    html = _single_dashboard_html(args.run)
    out = args.out or f"reports/{args.run}.analysis.pdf"
    path = export_pdf(html, out)
    print(f"pdf={path}")
    return 0


def _dashboard(args) -> int:
    from nylb.report.server import make_server
    lens_keys = [s.strip() for s in args.lenses.split(",") if s.strip()]
    server = make_server(port=args.port, lens_keys=lens_keys, lenses_file=args.lenses_file)
    host, port = server.server_address
    print(f"dashboard http://127.0.0.1:{port}  ('스캔 실행' 버튼으로 수집 · 탭: {', '.join(lens_keys)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0
