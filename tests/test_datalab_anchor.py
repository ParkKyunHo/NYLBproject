from datetime import datetime, timezone
from nylb.collectors import naver_datalab

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def _series(vals):
    return [{"period": f"2026-05-{i+1:02d}", "ratio": v} for i, v in enumerate(vals)]


def test_anchor_rescales_across_batches(monkeypatch):
    # 6 non-anchor terms → with batch_size=4: batch1 = anchor+t1..t4, batch2 = anchor+t5,t6.
    def fake_post(url, json, headers, timeout):
        names = [g["groupName"] for g in json["keywordGroups"]]
        if "t5" in names:           # batch2: anchor raw mean 10, t5 raw 80
            base = {"베이글": _series([10, 10, 10]), "t5": _series([80, 80, 80]),
                    "t6": _series([10, 10, 10])}
        else:                        # batch1: anchor raw mean 50, t1 raw 25
            base = {"베이글": _series([50, 50, 50]), "t1": _series([25, 25, 25]),
                    "t2": _series([50, 50, 50]), "t3": _series([50, 50, 50]),
                    "t4": _series([50, 50, 50])}
        return _FakeResp({"results": [{"title": n, "data": base[n]} for n in names]})
    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    q = {"keywords": ["베이글"], "anchor": "베이글",
         "radar_watchlist": ["t1", "t2", "t3", "t4", "t5", "t6"]}
    res = naver_datalab.collect(q, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    assert abs(by["베이글"] - 100) < 1
    assert abs(by["t1"] - 50) < 1     # batch1: 25 vs anchor 50 → 50
    assert abs(by["t5"] - 800) < 1    # batch2: 80 vs anchor 10 → 800


def test_one_batch_failure_keeps_others(monkeypatch):
    def fake_post(url, json, headers, timeout):
        names = [g["groupName"] for g in json["keywordGroups"]]
        if "t5" in names:
            raise RuntimeError("read timed out")   # batch2 fails
        base = {n: _series([10, 10, 10]) for n in names}
        return _FakeResp({"results": [{"title": n, "data": base[n]} for n in names]})
    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    q = {"keywords": ["베이글"], "anchor": "베이글",
         "radar_watchlist": ["t1", "t2", "t3", "t4", "t5", "t6"]}
    res = naver_datalab.collect(q, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    titles = {it.title for it in res.items}
    assert "t1" in titles and "베이글" in titles    # batch1 survived
    assert "t5" not in titles                        # failed batch's terms dropped
    assert len(res.errors) == 1                       # partial error surfaced, not fatal


def test_no_anchor_falls_back_to_legacy(monkeypatch):
    def fake_post(url, json, headers, timeout):
        names = [g["groupName"] for g in json["keywordGroups"]]
        return _FakeResp({"results": [{"title": t, "data": _series([10, 20, 30])} for t in names]})
    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    q = {"keywords": ["베이글"], "radar_watchlist": ["말차"]}
    res = naver_datalab.collect(q, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    assert by["베이글"] == 30.0 and by["말차"] == 30.0
