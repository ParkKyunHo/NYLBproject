from nylb.report.writer import write_text_report


def test_write_text_report(tmp_path):
    path = write_text_report("# 리포트\n내용", "run1", out_dir=tmp_path, suffix=".md")
    assert path.name == "run1.md"
    assert path.read_text(encoding="utf-8").startswith("# 리포트")


def test_write_creates_dir(tmp_path):
    target = tmp_path / "nested"
    path = write_text_report("x", "r", out_dir=target, suffix=".digest.md")
    assert path.name == "r.digest.md" and path.exists()
