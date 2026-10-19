import shutil
from pathlib import Path

from ..state.schemas import RefactorState


def patch_applier_node(state: RefactorState) -> RefactorState:
    """Write aggregated file patches to disk."""
    repository_path = Path(state["repository_path"])
    file_patches = state.get("file_patches", {})

    for module_path, new_code in file_patches.items():
        full_path = repository_path / module_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.is_file():
            backup_path = full_path.with_suffix(full_path.suffix + ".bak")
            if not backup_path.exists():
                shutil.copy2(full_path, backup_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_code)

    return state