from __future__ import annotations

from pathlib import Path
from typing import Protocol

from nylb.core.schema import ScanResult


class Store(Protocol):
    def save(self, result: ScanResult) -> Path: ...
    def load(self, run_id: str) -> ScanResult: ...


class LocalJsonStore:
    """Phase 1 storage. SaaS swaps this for a SupabaseStore behind the same Protocol."""

    def __init__(self, base_dir: Path | str = "data/raw") -> None:
        self.base_dir = Path(base_dir)

    def save(self, result: ScanResult) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{result.run_id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, run_id: str) -> ScanResult:
        path = self.base_dir / f"{run_id}.json"
        return ScanResult.model_validate_json(path.read_text(encoding="utf-8"))
