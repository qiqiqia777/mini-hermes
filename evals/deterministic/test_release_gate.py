"""The release gate must preserve Unicode output from its pytest subprocess."""

from minihermes.ops import release_gate


def test_run_preserves_unicode_under_legacy_child_encoding(tmp_path, monkeypatch, capsys):
    suite = tmp_path / "evals" / "unicode_output"
    suite.mkdir(parents=True)
    (suite / "test_failure.py").write_text(
        "def test_failure():\n    assert False, '中文测试输出'\n", encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "REPO", tmp_path)
    monkeypatch.setenv("PYTHONIOENCODING", "gbk")

    code, counts = release_gate.run("unicode_output")

    assert code == 1
    assert counts == {"passed": 0, "failed": 1}
    assert "中文测试输出" in capsys.readouterr().out
