from pathlib import Path

from src.self_healing_refactor.nodes.pytest_validator import run_pytest


def test_validator_runs_pytest_and_parses_json_report_on_windows(tmp_path: Path):
    (tmp_path / "test_sample.py").write_text(
        "def test_sample_passes():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )

    result = run_pytest(str(tmp_path))

    assert result["return_code"] == 0
    assert result["tests"]["test_sample.py::test_sample_passes"]["passed"] is True
