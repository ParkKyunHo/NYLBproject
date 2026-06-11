from __future__ import annotations

import json
from pathlib import Path

# Board persistence + scan-over-scan comparison. Storage is one JSON per run
# under data/boards/ (gitignored) — the same board contract the web lift will
# read, so history doubles as the Supabase/Actions seam later.

_DIR = Path("data/boards")


def save_board(board: dict, out_dir: str | Path | None = None) -> Path:
    d = Path(out_dir or _DIR)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{board['meta']['run_id']}.board.json"
    path.write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
    return path


def load_previous(lens: str, current_run_id: str,
                  out_dir: str | Path | None = None) -> dict | None:
    """Most recent stored board for `lens` other than the current run."""
    d = Path(out_dir or _DIR)
    if not d.exists():
        return None
    cands = [p for p in d.glob(f"*-{lens}-*.board.json")
             if p.name != f"{current_run_id}.board.json"]
    if not cands:
        return None
    latest = max(cands, key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return None


def compare_boards(prev: dict | None, cur: dict) -> dict | None:
    """Pure scan-over-scan delta: interest-rank moves + opportunity-score moves.
    Observation only — describes what changed, never what to do about it."""
    if not prev:
        return None
    prev_rank = {r["term"]: i + 1
                 for i, r in enumerate(prev.get("interest_ranking", []))}
    rank_moves: dict[str, dict] = {}
    for i, r in enumerate(cur.get("interest_ranking", [])):
        term, cur_pos = r["term"], i + 1
        prev_pos = prev_rank.get(term)
        rank_moves[term] = {
            "prev": prev_pos, "cur": cur_pos,
            "move": (prev_pos - cur_pos) if prev_pos is not None else None,
            "new": prev_pos is None,
        }
    prev_score = {o["term"]: o["opportunity"]["score"]
                  for o in prev.get("opportunities", [])}
    score_moves = {o["term"]: round(o["opportunity"]["score"] - prev_score[o["term"]], 1)
                   for o in cur.get("opportunities", []) if o["term"] in prev_score}
    return {"prev_run_id": prev["meta"]["run_id"],
            "prev_date": prev["meta"]["collected"],
            "rank_moves": rank_moves, "score_moves": score_moves}
