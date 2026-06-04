# SaaS MVP Slice 1 — Supabase Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist scan results to Supabase Postgres (multi-tenant) via a new `SupabaseStore` that satisfies the existing `Store` seam, opt-in from the CLI, with the current local flow preserved as default.

**Architecture:** The Postgres schema (`stores`, `scan_results`, RLS) is already applied to project `tvkhyqgpfiytrzlpkszp` via Supabase MCP. This plan adds the Python side only: a `supabase` dependency, a return-type widening of `Store.save` (Path→str) so both stores share one contract, `SupabaseStore` (supabase-py client, injectable for testing), and a `--store-backend [local|supabase]` CLI flag. No paid LLM API is involved — analysis stays as-is.

**Tech Stack:** Python 3.12, Pydantic v2, supabase-py, pytest. Run with `.\.venv\Scripts\python.exe` (the Bash tool mangles the Windows venv path — use the PowerShell tool for python/pytest/git).

**Spec:** `docs/superpowers/specs/2026-06-04-nylb-saas-mvp-design.md` (slice 1)

**Conventions:** Tests unit-test behavior with hand-written fakes (no network). Commit after each green task. Branch: `feat/supabase-persistence`.

---

## File Structure

| File | Responsibility | Create/Modify |
|------|----------------|---------------|
| `pyproject.toml` | add `supabase` dependency | Modify |
| `src/nylb/core/store.py` | widen `Store.save`→str; add `SupabaseStore` | Modify |
| `src/nylb/config.py` | expose `supabase_url`/`supabase_service_key` | Modify |
| `src/nylb/cli.py` | `_make_store()` + `--store-backend` flag | Modify |
| `tests/core/test_store.py` | adapt local test; add SupabaseStore tests | Modify |
| `tests/test_config.py` | supabase settings test | Modify |
| `tests/test_cli.py` | store-selection test | Modify |

---

## Task 1: Add the `supabase` dependency

**Files:**
- Modify: `pyproject.toml:6-12`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, change the `dependencies` list to add `supabase`:

```toml
dependencies = [
  "pydantic>=2.6",
  "httpx>=0.27",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
  "pytrends>=4.9",
  "supabase>=2.4",
]
```

- [ ] **Step 2: Install it**

Run: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
Expected: installs `supabase` and its deps (gotrue/postgrest/realtime/storage3), ends with `Successfully installed ...`.

- [ ] **Step 3: Verify import**

Run: `.\.venv\Scripts\python.exe -c "import supabase; print(supabase.__version__)"`
Expected: prints a version (e.g., `2.x.x`), no ImportError.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add supabase-py dependency"
```

---

## Task 2: Widen `Store.save` return type (Path → str)

`SupabaseStore` has no filesystem path to return, so the `Store` contract returns a `str` locator. `LocalJsonStore.save` returns `str(path)`; the roundtrip test must wrap it in `Path(...)`.

**Files:**
- Modify: `src/nylb/core/store.py:9-24`
- Test: `tests/core/test_store.py:16-19`

- [ ] **Step 1: Update the failing test first**

In `tests/core/test_store.py`, add `from pathlib import Path` to the imports (top of file) and change `test_save_then_load_roundtrip` so the locator is wrapped:

```python
def test_save_then_load_roundtrip(tmp_path):
    store = LocalJsonStore(base_dir=tmp_path)
    loc = store.save(_result("abc"))
    assert isinstance(loc, str)          # contract is now a str locator
    assert Path(loc).exists()
    loaded = store.load("abc")
    assert loaded.run_id == "abc"
    assert loaded.items[0].title == "베이글"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_store.py::test_save_then_load_roundtrip -v`
Expected: FAIL — `assert isinstance(loc, str)` fails because `save` currently returns a `Path`.

- [ ] **Step 3: Update `Store` Protocol and `LocalJsonStore.save`**

In `src/nylb/core/store.py`, change the `Store` Protocol `save` annotation and `LocalJsonStore.save` to return a str:

```python
class Store(Protocol):
    def save(self, result: ScanResult) -> str: ...
    def load(self, run_id: str) -> ScanResult: ...
```

and in `LocalJsonStore.save`, change the final lines:

```python
    def save(self, result: ScanResult) -> str:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{result.run_id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_store.py -v`
Expected: PASS (both store tests). `run_scan` ignores `save()`'s return, so no caller breaks.

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/store.py tests/core/test_store.py
git commit -m "refactor: Store.save returns a str locator (Path->str)"
```

---

## Task 3: `SupabaseStore` (Store seam over Postgres)

**Files:**
- Modify: `src/nylb/core/store.py` (append `SupabaseStore`)
- Test: `tests/core/test_store.py` (append fake + tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_store.py -k supabase -v`
Expected: FAIL — `ImportError`/`AttributeError`: `SupabaseStore` not defined.

- [ ] **Step 3: Implement `SupabaseStore`**

Append to `src/nylb/core/store.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_store.py -v`
Expected: PASS (local + 3 supabase tests).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/store.py tests/core/test_store.py
git commit -m "feat: add SupabaseStore (Store seam over Postgres)"
```

---

## Task 4: Config settings + CLI `--store-backend` flag

**Files:**
- Modify: `src/nylb/config.py:13-19`
- Modify: `src/nylb/cli.py` (imports, `_make_store`, scan parser + store selection)
- Test: `tests/test_config.py`, `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_load_settings_includes_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    from nylb.config import load_settings
    s = load_settings()
    assert s["supabase_url"] == "https://x.supabase.co"
    assert s["supabase_service_key"] == "svc-key"
```

Append to `tests/test_cli.py`:

```python
def test_make_store_local_is_default():
    from nylb.cli import _make_store
    from nylb.core.store import LocalJsonStore
    assert isinstance(_make_store("local", "nylb", {}), LocalJsonStore)


def test_make_store_supabase_passes_settings(monkeypatch):
    from nylb import cli
    captured = {}

    class FakeSB:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(cli, "SupabaseStore", FakeSB)
    store = cli._make_store("supabase", "nylb",
                            {"supabase_url": "u", "supabase_service_key": "k"})
    assert isinstance(store, FakeSB)
    assert captured == {"url": "u", "service_key": "k", "store_key": "nylb"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py::test_load_settings_includes_supabase tests/test_cli.py -k "make_store or supabase" -v`
Expected: FAIL — `KeyError: 'supabase_url'` and `AttributeError: module 'nylb.cli' has no attribute '_make_store'`.

- [ ] **Step 3a: Add settings keys**

In `src/nylb/config.py`, add two entries to the dict returned by `load_settings()`:

```python
    return {
        "youtube_api_key": os.getenv("YOUTUBE_API_KEY"),
        "naver_client_id": os.getenv("NAVER_CLIENT_ID"),
        "naver_client_secret": os.getenv("NAVER_CLIENT_SECRET"),
        "instagram_graph_token": os.getenv("INSTAGRAM_GRAPH_TOKEN"),
        "instagram_user_id": os.getenv("INSTAGRAM_USER_ID"),
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_service_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    }
```

- [ ] **Step 3b: Add `_make_store` + import to cli.py**

In `src/nylb/cli.py`, add `SupabaseStore` to the store import:

```python
from nylb.core.store import LocalJsonStore, SupabaseStore
```

Add the helper at module level (e.g., after `build_run_id`):

```python
def _make_store(backend: str, store_key: str, settings: dict):
    if backend == "supabase":
        return SupabaseStore(url=settings.get("supabase_url"),
                             service_key=settings.get("supabase_service_key"),
                             store_key=store_key)
    return LocalJsonStore()
```

- [ ] **Step 3c: Wire the flag into the scan command**

In `src/nylb/cli.py`, add the argument to the scan parser (next to `--store`):

```python
    scan_p.add_argument("--store-backend", choices=["local", "supabase"], default="local")
```

and in the scan logic, replace `store=LocalJsonStore()` in the `run_scan(...)` call with the selected store:

```python
    store = _make_store(args.store_backend, args.store, settings)
    result = run_scan(
        args.lens, store_id=args.store, lens_config=lens_config, settings=settings,
        store=store, run_id=run_id, collected_at=now,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_cli.py -v`
Expected: PASS (config + cli tests, including the existing report-html test).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/config.py src/nylb/cli.py tests/test_config.py tests/test_cli.py
git commit -m "feat: --store-backend supabase flag + supabase settings"
```

---

## Task 5: Full-suite + live verification (controller — needs real keys)

**Files:** none (verification only). This task is run by the controller, not a subagent, because it needs the real Supabase service_role key in `.env`.

- [ ] **Step 1: Full suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS — all tests green (no regressions; supabase tests use fakes).

- [ ] **Step 2: Confirm `.env` has Supabase creds**

`.env` must contain `SUPABASE_URL=https://tvkhyqgpfiytrzlpkszp.supabase.co` and `SUPABASE_SERVICE_ROLE_KEY=<from dashboard Settings→API>`. If absent, stop and ask the user to add them.

- [ ] **Step 3: Live persist + verify**

Run: `.\.venv\Scripts\python.exe -m nylb scan --lens menu --store nylb --store-backend supabase`
Expected: scan completes; a row lands in `scan_results`.

Verify via Supabase MCP `execute_sql` on project `tvkhyqgpfiytrzlpkszp`:
`select store_id, run_id, lens, created_at from scan_results order by created_at desc limit 3;`
Expected: the new run_id appears, linked to a `stores` row with `store_key='nylb'`.

- [ ] **Step 4: Finish the branch**

Use `superpowers:finishing-a-development-branch` (merge `feat/supabase-persistence` → `main` + push).

---

## Self-Review (completed during planning)

- **Spec coverage:** schema (already applied via MCP, §5.2) ✓; SupabaseStore §5.3 → Task 3; Store.save→str §5.3 → Task 2; config+CLI §5.4 → Task 4; supabase dep §5.6 → Task 1; acceptance §6 → Task 5. All slice-1 spec items mapped. ✓
- **Placeholder scan:** no TBD/"handle errors" placeholders; SupabaseStore error path is explicit `RuntimeError`; every code step shows full code. ✓
- **Type consistency:** `Store.save -> str` (Task 2) matches `SupabaseStore.save -> str` and `LocalJsonStore.save -> str`; `SupabaseStore(url=, service_key=, store_key=, client=)` signature matches the `_make_store` kwargs (Task 4) and the test (`captured == {"url","service_key","store_key"}`); `_make_store(backend, store_key, settings)` matches the CLI call site. ✓
