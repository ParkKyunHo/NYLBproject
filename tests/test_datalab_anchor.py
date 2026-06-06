from datetime import datetime, timezone

from nylb.collectors import naver_datalab

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def _series(vals):
    return [{"period": f"2026-05-{i+1:02d}", "ratio": v} for i, v in enumerate(vals)]


def test_anchor_rescales_terms_to_common_scale(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        groups = [g["groupName"] for g in json["keywordGroups"]]
        calls.append(groups)
        if "성심당" in groups:
            data = {"베이글": _series([10, 10, 10]), "성심당": _series([80, 80, 80])}
        else:
            data = {"베이글": _series([50, 50, 50]), "말차": _series([25, 25, 25])}
        return _FakeResp({"results": [{"title": t, "data": data[t]} for t in groups]})

    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    query = {"keywords": ["베이글"], "radar_watchlist": ["말차", "성심당"], "anchor": "베이글"}
    res = naver_datalab.collect(query, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    assert abs(by["베이글"] - 100) < 1
    assert abs(by["말차"] - 50) < 1
    assert abs(by["성심당"] - 800) < 1


def test_no_anchor_falls_back_to_legacy(monkeypatch):
    def fake_post(url, json, headers, timeout):
        groups = [g["groupName"] for g in json["keywordGroups"]]
        return _FakeResp({"results": [{"title": t, "data": _series([10, 20, 30])} for t in groups]})
    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    query = {"keywords": ["베이글"], "radar_watchlist": ["말차"]}
    res = naver_datalab.collect(query, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    assert by["베이글"] == 30.0 and by["말차"] == 30.0
