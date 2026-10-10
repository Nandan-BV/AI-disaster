from pathlib import Path
from types import SimpleNamespace

from src.self_healing_refactor.graph.builder import (
    build_refactor_graph,
    create_initial_state,
)
from src.self_healing_refactor.nodes import refactor_worker


def test_refactor_graph_compiles_with_worker_node_and_edges():
    graph = build_refactor_graph(max_retries=2)
    graph_nodes = graph.get_graph().nodes

    assert "refactor_worker" in graph_nodes
    assert "patch_applier_node" in graph_nodes
    assert "pytest_validation_node" in graph_nodes


def test_refactor_graph_runs_with_a_local_mocked_worker(tmp_path: Path, monkeypatch):
    package = tmp_path / "mypackage"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calc.py").write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text(
        "from mypackage.calc import add\n\n"
        "def test_add():\n"
        "    assert add(4, 2) == 6\n",
        encoding="utf-8",
    )

    class FakeChatOpenAI:
        def __init__(self, **_kwargs):
            pass

        def invoke(self, _messages):
            return SimpleNamespace(content="def add(a, b):\n    return a + b\n")

    monkeypatch.setattr(refactor_worker, "ChatOpenAI", FakeChatOpenAI)
    state = create_initial_state(str(tmp_path), max_retries=2)
    state["test_results"] = {
        "tests/test_calc.py::test_add": {
            "failed": True,
            "traceback": "mypackage.calc failed",
            "error": "wrong result",
        }
    }

    final_state = build_refactor_graph(max_retries=2).invoke(state)

    assert final_state["test_results"]["return_code"] == 0
    assert final_state["file_patches"] == {
        str(Path("mypackage") / "calc.py"): "def add(a, b):\n    return a + b"
    }
    assert (package / "calc.py.bak").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a - b\n"
    )
