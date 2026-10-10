from typing import Annotated, Any, Dict, List
from typing_extensions import TypedDict


class ModuleState(TypedDict):
    """State for individual module refactoring worker."""
    module_path: str
    repository_path: str
    test_results: Dict[str, Any]


def merge_patches(existing: Dict[str, str], new_patches: Dict[str, str]) -> Dict[str, str]:
    """Merge worker patch maps, preferring the newest code for each path."""
    return {**existing, **new_patches}


class RefactorState(TypedDict):
    """Base state for the refactoring engine."""
    repository_path: str
    modules_to_refactor: List[str]
    ast_dependency_map: Dict[str, List[str]]
    file_patches: Annotated[Dict[str, str], merge_patches]
    test_results: Dict[str, Any]
    retry_count: int
    max_retries: int