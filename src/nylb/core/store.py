from __future__ import annotations

from pathlib import Path
from typing import Protocol

from nylb.core.schema import ScanResult


class Store(Protocol):
    def save(self, result: ScanResult) -> str: ...
    def load(self, run_id: str) -> ScanResult: ...


class LocalJsonStore:
    """Phase 1 storage. SaaS swaps this for a SupabaseStore behind the same Protocol."""

    def __init__(self, base_dir: Path | str = "data/raw") -> None:
        self.base_dir = Path(base_dir)

    def save(self, result: ScanResult) -> str:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{result.run_id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def load(self, run_id: str) -> ScanResult:
        path = self.base_dir / f"{run_id}.json"
        return ScanResult.model_validate_json(path.read_text(encoding="utf-8"))


class SupabaseStore:
    """SaaS storage: persists ScanResult payloads to Supabase Postgres
    behind the same Store Protocol. `client` is injectable for tests."""

    def __init__(self, url: str | None = None, service_key: str | None = None,
                 store_key: str = "nylb", client=None) -> None:
        if client is None:
            if not (url and service_key):
                raise RuntimeError("Supabase url/service_key required")
            from supabase import create_client
            client = create_client(url, service_key)
        self.client = client
        self.store_key = store_key

    def _store_id(self) -> str:
        self.client.table("stores").upsert(
            {"store_key": self.store_key}, on_conflict="store_key").execute()
        res = (self.client.table("stores").select("id")
               .eq("store_key", self.store_key).single().execute())
        return res.data["id"]

    def save(self, result: ScanResult) -> str:
        store_id = self._store_id()
        self.client.table("scan_results").upsert({
            "store_id": store_id,
            "run_id": result.run_id,
            "lens": result.lens,
            "payload": result.model_dump(mode="json"),
        }, on_conflict="store_id,run_id").execute()
        return f"supabase://{self.store_key}/{result.run_id}"

    def load(self, run_id: str) -> ScanResult:
        store_id = self._store_id()
        res = (self.client.table("scan_results").select("payload")
               .eq("store_id", store_id).eq("run_id", run_id).single().execute())
        return ScanResult.model_validate(res.data["payload"])
