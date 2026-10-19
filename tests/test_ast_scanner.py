from pathlib import Path

from src.self_healing_refactor.nodes.ast_scanner import build_dependency_map
from src.self_healing_refactor.state.schemas import merge_patches


def test_build_dependency_map_extracts_local_import_dependencies(tmp_path: Path):
    package = tmp_path / "mypackage"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text("class Model: pass\n", encoding="utf-8")
    (package / "helpers.py").write_text("def helper(): pass\n", encoding="utf-8")
    (package / "consumer.py").write_text(
        "import mypackage.helpers\nfrom mypackage import models\n",
        encoding="utf-8",
    )

    dependency_map = build_dependency_map(str(tmp_path))

    assert dependency_map[str(Path("mypackage") / "consumer.py")] == [
        str(Path("mypackage") / "helpers.py"),
        str(Path("mypackage") / "models.py"),
    ]


def test_merge_patches_combines_paths_and_prefers_newer_patch():
    merged = merge_patches(
        {"pkg/a.py": "old-a", "pkg/b.py": "b"},
        {"pkg/a.py": "new-a", "pkg/c.py": "c"},
    )

    assert merged == {
        "pkg/a.py": "new-a",
        "pkg/b.py": "b",
        "pkg/c.py": "c",
    }
