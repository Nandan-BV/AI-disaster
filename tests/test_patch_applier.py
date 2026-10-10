from pathlib import Path

from src.self_healing_refactor.nodes.patch_applier import patch_applier_node


def test_patch_applier_backs_up_original_and_preserves_first_backup(tmp_path: Path):
    source = tmp_path / "package" / "module.py"
    source.parent.mkdir()
    source.write_text("original = True\n", encoding="utf-8")
    state = {
        "repository_path": str(tmp_path),
        "file_patches": {"package/module.py": "updated = True\n"},
    }

    patch_applier_node(state)
    backup = source.with_suffix(".py.bak")
    assert source.read_text(encoding="utf-8") == "updated = True\n"
    assert backup.read_text(encoding="utf-8") == "original = True\n"

    patch_applier_node(
        {
            **state,
            "file_patches": {"package/module.py": "updated_again = True\n"},
        }
    )
    assert source.read_text(encoding="utf-8") == "updated_again = True\n"
    assert backup.read_text(encoding="utf-8") == "original = True\n"
