from typing import Annotated, Any, Dict, List
from typing_extensions import TypedDict
<<<<<<< HEAD


def merge_file_patches(left: Dict[str, str], right: Dict[str, str]) -> Dict[str, str]:
    return {**left, **right}
=======
>>>>>>> origin/main


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
<<<<<<< HEAD
    file_patches: Annotated[Dict[str, str], merge_file_patches]
=======
    file_patches: Annotated[Dict[str, str], merge_patches]
>>>>>>> origin/main
    test_results: Dict[str, Any]
    retry_count: int
    max_retries: int