from typing import Dict, List, Any, Annotated
from typing_extensions import TypedDict
from langgraph.graph import add_messages
from langgraph.graph.message import merge_dict_reducer


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
    file_patches: Annotated[Dict[str, str], merge_dict_reducer]
    test_results: Dict[str, Any]
    retry_count: int
    max_retries: int