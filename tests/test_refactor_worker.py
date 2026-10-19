from pathlib import Path
from types import SimpleNamespace

from src.self_healing_refactor.nodes import refactor_worker


def test_worker_wraps_module_patch_under_file_patches(tmp_path: Path, monkeypatch):
    source = tmp_path / "mypackage" / "module.py"
    source.parent.mkdir()
    source.write_text("value = 1\n", encoding="utf-8")

    class FakeChatOpenAI:
        def __init__(self, **_kwargs):
            pass

        def invoke(self, _messages):
            return SimpleNamespace(content="value = 2\n")

    monkeypatch.setattr(refactor_worker, "ChatOpenAI", FakeChatOpenAI)
    result = refactor_worker.parallel_refactor_worker(
        {
            "module_path": "mypackage/module.py",
            "repository_path": str(tmp_path),
            "test_results": {},
        }
    )

    assert result == {"file_patches": {"mypackage/module.py": "value = 2"}}
