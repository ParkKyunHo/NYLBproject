from nylb.core.season import monthly_profile, season_summary


def _series(month_values: dict[str, float]) -> list[dict]:
    return [{"date": f"{ym}-01", "value": v} for ym, v in month_values.items()]


def test_monthly_profile_normalizes_to_mean_100():
    # 3 years, December always 3x the other months
    data = {}
    for y in (2023, 2024, 2025):
        for m in range(1, 13):
            data[f"{y}-{m:02d}"] = 30.0 if m == 12 else 10.0
    prof = monthly_profile(_series(data))
    assert len(prof) == 12
    mean = sum(prof.values()) / 12
    assert abs(mean - 100.0) < 0.5
    assert prof[12] > prof[1] * 2.5  # December clearly peaks


def test_monthly_profile_empty_and_zero_series():
    assert monthly_profile([]) == {}
    flat0 = _series({f"2025-{m:02d}": 0.0 for m in range(1, 13)})
    prof = monthly_profile(flat0)
    assert all(v == 0.0 for v in prof.values())


def test_season_summary_in_season():
    prof = {m: (160.0 if m in (6, 7) else 90.0) for m in range(1, 13)}
    s = season_summary(prof, month_now=6)
    assert s["status"] == "in_season"
    assert set(s["peak_months"]) == {6, 7}
    assert s["now_index"] == 160.0


def test_season_summary_entering_looks_ahead_two_months():
    prof = {m: (170.0 if m == 8 else 90.0) for m in range(1, 13)}
    assert season_summary(prof, month_now=6)["status"] == "entering"  # +2 months
    assert season_summary(prof, month_now=7)["status"] == "entering"  # +1 month
    assert season_summary(prof, month_now=9)["status"] == "off"


def test_season_summary_year_wraparound():
    prof = {m: (150.0 if m == 1 else 95.0) for m in range(1, 13)}
    s = season_summary(prof, month_now=12)
    assert s["status"] == "entering"
    assert s["next_index"] == 150.0


def test_season_summary_no_data_and_low_coverage():
    assert season_summary({}, month_now=6)["status"] == "no_data"
    partial = {m: 100.0 for m in range(1, 7)}  # only 6 months
    s = season_summary(partial, month_now=6)
    assert s["coverage_months"] == 6
    assert s["low_coverage"] is True


def test_season_summary_flat_profile_is_off_not_peaky():
    prof = {m: 100.0 for m in range(1, 13)}
    s = season_summary(prof, month_now=6)
    assert s["status"] == "off"
    assert s["peak_months"] == []
