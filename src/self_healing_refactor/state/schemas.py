from typing import Dict, List, Any, Annotated
from typing_extensions import TypedDict


def merge_file_patches(left: Dict[str, str], right: Dict[str, str]) -> Dict[str, str]:
    return {**left, **right}


class ModuleState(TypedDict):
    """State for individual module refactoring worker."""
    module_path: str
    repository_path: str
    test_results: Dict[str, Any]


class RefactorState(TypedDict):
    """Base state for the refactoring engine."""
    repository_path: str
    modules_to_refactor: List[str]
    ast_dependency_map: Dict[str, List[str]]
    file_patches: Annotated[Dict[str, str], merge_file_patches]
    test_results: Dict[str, Any]
    retry_count: int
    max_retries: int