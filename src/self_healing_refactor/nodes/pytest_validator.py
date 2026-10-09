import subprocess
import json
from pathlib import Path
from typing import Dict, Any

from ..state.schemas import RefactorState


def run_pytest(repository_path: str) -> Dict[str, Any]:
    """Run pytest and capture results."""
    repo_path = Path(repository_path)
    result = subprocess.run(
        ["python", "-m", "pytest", "--tb=short", "-v", "--json-report", "--json-report-file=/dev/stdout"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120
    )

    test_results: Dict[str, Any] = {
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "tests": {}
    }

    try:
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.strip().startswith("{"):
                    try:
                        report = json.loads(line)
                        if "tests" in report:
                            for test in report["tests"]:
                                test_results["tests"][test["nodeid"]] = {
                                    "passed": test["outcome"] == "passed",
                                    "failed": test["outcome"] == "failed",
                                    "error": test.get("call", {}).get("longrepr", ""),
                                    "traceback": test.get("call", {}).get("traceback", [])
                                }
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return test_results


def pytest_validation_node(state: RefactorState) -> RefactorState:
    """Run pytest validation and capture results."""
    repository_path = state["repository_path"]
    test_results = run_pytest(repository_path)

    return {
        **state,
        "test_results": test_results
    }