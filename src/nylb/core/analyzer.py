from __future__ import annotations

from typing import Protocol

from nylb.core.schema import Item, ScanResult


def _engagement(item: Item) -> float:
    m = item.metrics
    return (m.get("views", 0) + m.get("likes", 0) * 10
            + m.get("comments", 0) * 20 + m.get("interest", 0) * 50)


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
