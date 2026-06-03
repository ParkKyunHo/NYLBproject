from __future__ import annotations

from typing import Protocol

from nylb.core.schema import Item, ScanResult


def _engagement(item: Item) -> float:
    m = item.metrics
    return (m.get("views", 0) + m.get("likes", 0) * 10
            + m.get("comments", 0) * 20 + m.get("interest", 0) * 50)


def cross_channel_terms(result: ScanResult, top_n: int = 10) -> list[dict]:
    """Rank candidate terms by how many distinct channels mention them.

    Candidates = lens keywords + instagram hashtags + google_trends terms.
    The strongest trend signal is a term that surfaces across several channels
    at once, so terms are ranked by channel breadth first, then engagement.
    """
    candidates: set[str] = set(result.query.get("keywords", []) or [])
    candidates |= set(result.query.get("instagram_hashtags", []) or [])
    for item in result.items:
        if item.source == "google_trends":
            candidates.add(item.title)

    rows: list[dict] = []
    for term in candidates:
        needle = term.lower()
        channels: set[str] = set()
        engagement = 0.0
        for item in result.items:
            haystack = f"{item.title} {item.text or ''}".lower()
            if needle in haystack:
                channels.add(item.source)
                engagement += _engagement(item)
        if channels:
            rows.append({
                "term": term,
                "channels": sorted(channels),
                "channel_count": len(channels),
                "engagement": engagement,
            })
    rows.sort(key=lambda r: (r["channel_count"], r["engagement"]), reverse=True)
    return rows[:top_n]


class Analyzer(Protocol):
    def prepare(self, result: ScanResult, top_n: int = 10) -> str: ...


class ClaudeCodeAnalyzer:
    """Phase 1 analyzer: builds a deterministic digest (no LLM call).
    The Claude Code session reads this digest and adds insight/actions.
    SaaS swaps in an ApiAnalyzer behind the same Protocol."""

    def prepare(self, result: ScanResult, top_n: int = 10) -> str:
        lines = [
            f"# Scan digest — {result.lens} ({result.run_id})",
            "",
            f"- store: {result.store_id}",
            f"- items: {len(result.items)}  errors: {len(result.errors)}",
        ]
        if result.errors:
            lines += ["", "## Collection errors"]
            lines += [f"- {e.source}: {e.message}" for e in result.errors]

        cross = cross_channel_terms(result, top_n=top_n)
        if cross:
            multi = [r for r in cross if r["channel_count"] >= 2]
            lines += ["", "## 🔥 채널 교차 핫 키워드"]
            if multi:
                for r in multi:
                    lines.append(
                        f"- **{r['term']}** — {r['channel_count']}개 채널 "
                        f"({', '.join(r['channels'])}), 인게이지먼트 {int(r['engagement'])}"
                    )
            else:
                lines.append("- (2개 이상 채널에서 동시 등장한 키워드 없음)")

        by_source: dict[str, list[Item]] = {}
        for item in result.items:
            by_source.setdefault(item.source, []).append(item)

        for source, items in by_source.items():
            ranked = sorted(items, key=_engagement, reverse=True)[:top_n]
            lines += ["", f"## {source} (top {len(ranked)})"]
            for it in ranked:
                metric_str = ", ".join(f"{k}={int(v)}" for k, v in it.metrics.items()) or "—"
                lines.append(f"- **{it.title}** [{metric_str}] {it.url or ''}".rstrip())
        return "\n".join(lines)
