from datetime import datetime, timezone
from pathlib import Path
from nylb.core.schema import Item, ScanResult
from nylb.core.store import LocalJsonStore


def _result(run_id="r1"):
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    return ScanResult(
        run_id=run_id, store_id="nylb", lens="menu", query={},
        items=[Item(source="youtube", lens="menu", type="video",
                    title="베이글", collected_at=now)],
        started_at=now, finished_at=now,
    )


def test_save_then_load_roundtrip(tmp_path):
    store = LocalJsonStore(base_dir=tmp_path)
    loc = store.save(_result("abc"))
    assert isinstance(loc, str)          # contract is now a str locator
    assert Path(loc).exists()
    loaded = store.load("abc")
    assert loaded.run_id == "abc"
    assert loaded.items[0].title == "베이글"


def test_save_creates_dir(tmp_path):
    target = tmp_path / "nested" / "raw"
    store = LocalJsonStore(base_dir=target)
    store.save(_result("x"))
    assert (target / "x.json").exists()


import pytest
from nylb.core.store import SupabaseStore


class _Resp:
    def __init__(self, data):
        self.data = data


class _Q:
    """Minimal fake of supabase-py's fluent table query."""
    def __init__(self, backing, table):
        self.backing, self.table = backing, table
        self._op = None
        self._eq = {}

    def upsert(self, row, on_conflict=None):
        self._op = ("upsert", row)
        return self

    def select(self, cols):
        self._op = ("select", cols)
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def single(self):
        return self

    def execute(self):
        op, arg = self._op
        if self.table == "stores":
            if op == "upsert":
                self.backing.stores[arg["store_key"]] = "store-uuid-1"
                return _Resp(None)
            return _Resp({"id": self.backing.stores.get(self._eq["store_key"], "store-uuid-1")})
        if self.table == "scan_results":
            if op == "upsert":
                self.backing.results[(arg["store_id"], arg["run_id"])] = arg["payload"]
                return _Resp(None)
            return _Resp({"payload": self.backing.results[(self._eq["store_id"], self._eq["run_id"])]})
        raise AssertionError(f"unexpected table {self.table}")


class FakeClient:
    def __init__(self):
        self.stores = {}
        self.results = {}

    def table(self, name):
        return _Q(self, name)


def test_supabase_store_roundtrip():
    store = SupabaseStore(store_key="nylb", client=FakeClient())
    loc = store.save(_result("abc"))
    assert loc == "supabase://nylb/abc"
    loaded = store.load("abc")
    assert loaded.run_id == "abc"
    assert loaded.items[0].title == "베이글"


def test_supabase_store_save_writes_payload_jsonb():
    client = FakeClient()
    SupabaseStore(store_key="nylb", client=client).save(_result("xyz"))
    payload = client.results[("store-uuid-1", "xyz")]
    assert isinstance(payload, dict)           # serialized to JSON-able dict, not a model
    assert payload["run_id"] == "xyz"


def test_supabase_store_requires_credentials():
    with pytest.raises(RuntimeError):
        SupabaseStore()                        # no client and no url/key
