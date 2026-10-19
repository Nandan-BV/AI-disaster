import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

from ..state.schemas import RefactorState


def run_pytest(repository_path: str) -> Dict[str, Any]:
    """Run pytest and capture results."""
    repo_path = Path(repository_path)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as report_file:
        report_path = Path(report_file.name)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--tb=short",
                "-v",
                "--json-report",
                f"--json-report-file={report_path}",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        test_results: Dict[str, Any] = {
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "tests": {},
        }
        for test in report.get("tests", []):
            call_result = test.get("call") or {}
            test_results["tests"][test["nodeid"]] = {
                "passed": test["outcome"] == "passed",
                "failed": test["outcome"] == "failed",
                "error": call_result.get("longrepr", ""),
                "traceback": call_result.get("traceback", ""),
            }
        return test_results
    finally:
        report_path.unlink(missing_ok=True)


def pytest_validation_node(state: RefactorState) -> RefactorState:
    """Run pytest validation and capture results."""
    repository_path = state["repository_path"]
    test_results = run_pytest(repository_path)

    return {
        **state,
        "test_results": test_results
    }