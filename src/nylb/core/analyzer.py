from __future__ import annotations

from typing import Protocol

from nylb.core.schema import ScanResult
from nylb.core.signal import _item_key, score_items


def cross_channel_terms(result: ScanResult, top_n: int = 10,
                        scores: dict[str, float] | None = None) -> list[dict]:
    """Rank candidate terms by how many distinct channels mention them, then by
    summed recency×popularity signal. Channel breadth is the strongest trend
    signal, so it stays primary; signal is the tiebreak."""
    if scores is None:
        scores = score_items(result, result.finished_at)

    candidates: set[str] = set(result.query.get("keywords", []) or [])
    candidates |= set(result.query.get("instagram_hashtags", []) or [])
    for item in result.items:
        if item.source == "google_trends":
            candidates.add(item.title)

    rows: list[dict] = []
    for term in candidates:
        needle = term.lower()
        channels: set[str] = set()
        signal = 0.0
        for item in result.items:
            haystack = f"{item.title} {item.text or ''}".lower()
            if needle in haystack:
                channels.add(item.source)
                signal += scores.get(_item_key(item), 0.0)
        if channels:
            rows.append({
                "term": term,
                "channels": sorted(channels),
                "channel_count": len(channels),
                "signal": round(signal, 3),
            })
    rows.sort(key=lambda r: (r["channel_count"], r["signal"]), reverse=True)
    return rows[:top_n]


class Analyzer(Protocol):
    def prepare(self, result: ScanResult, top_n: int = 10) -> str: ...


class ClaudeCodeAnalyzer:
    """Phase 1 analyzer: builds a deterministic digest (no LLM call).
    The Claude Code session reads this digest and adds insight/actions.
    SaaS swaps in an ApiAnalyzer behind the same Protocol."""

    def prepare(self, result: ScanResult, top_n: int = 10) -> str:
        scores = score_items(result, result.finished_at)
        lines = [
            f"# Scan digest — {result.lens} ({result.run_id})",
            "",
            f"- store: {result.store_id}",
            f"- items: {len(result.items)}  errors: {len(result.errors)}",
        ]
        if result.errors:
            lines += ["", "## Collection errors"]
            lines += [f"- {e.source}: {e.message}" for e in result.errors]

        if result.dropped_by_source:
            lines += ["", "## 🧹 관련성 필터로 제외"]
            lines += [f"- {s}: {n}건 (키워드 무관)"
                      for s, n in sorted(result.dropped_by_source.items())]

        cross = cross_channel_terms(result, top_n=top_n, scores=scores)
        if cross:
            multi = [r for r in cross if r["channel_count"] >= 2]
            lines += ["", "## 🔥 채널 교차 핫 키워드"]
            if multi:
                for r in multi:
                    lines.append(
                        f"- **{r['term']}** — {r['channel_count']}개 채널 "
                        f"({', '.join(r['channels'])}), 신호 {r['signal']}"
                    )
            else:
                lines.append("- (2개 이상 채널에서 동시 등장한 키워드 없음)")

        by_source: dict[str, list] = {}
        for item in result.items:
            by_source.setdefault(item.source, []).append(item)

        for source, items in by_source.items():
            ranked = sorted(items, key=lambda it: scores.get(_item_key(it), 0.0),
                            reverse=True)[:top_n]
            lines += ["", f"## {source} (top {len(ranked)})"]
            for it in ranked:
                metric_str = ", ".join(f"{k}={int(v)}" for k, v in it.metrics.items()) or "—"
                lines.append(f"- **{it.title}** [{metric_str}] {it.url or ''}".rstrip())
        return "\n".join(lines)
