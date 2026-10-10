from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from ..state.schemas import RefactorState, ModuleState
from ..nodes.ast_scanner import ast_scanner_node
from ..nodes.refactor_worker import parallel_refactor_worker
from ..nodes.patch_applier import patch_applier_node
from ..nodes.pytest_validator import pytest_validation_node
from ..graph.routing import route_after_validation


def create_refactor_worker_graph() -> StateGraph:
    """Create the subgraph for parallel module refactoring."""
    worker_graph = StateGraph(ModuleState)
    worker_graph.add_node("refactor_worker", parallel_refactor_worker)
    worker_graph.set_entry_point("refactor_worker")
    worker_graph.set_finish_point("refactor_worker")
    return worker_graph


def map_refactor_workers(state: RefactorState):
    """Map refactor workers across modules_to_refactor."""
    modules = state.get("modules_to_refactor", [])
    repository_path = state.get("repository_path", "")
    test_results = state.get("test_results", {})

    sends = []
    for module_path in modules:
        sends.append(Send("refactor_worker", {
            "module_path": module_path,
            "repository_path": repository_path,
            "test_results": test_results
        }))
    return sends


def build_refactor_graph(max_retries: int = 3) -> StateGraph:
    """Build the main self-healing refactoring graph."""
    graph = StateGraph(RefactorState)

    graph.add_node("ast_scanner_node", ast_scanner_node)
    graph.add_node("refactor_worker", parallel_refactor_worker)
    graph.add_node("patch_applier_node", patch_applier_node)
    graph.add_node("pytest_validation_node", pytest_validation_node)

    graph.add_edge(START, "ast_scanner_node")

    graph.add_conditional_edges(
        "ast_scanner_node",
        map_refactor_workers,
        ["refactor_worker"]
    )

    graph.add_edge("refactor_worker", "patch_applier_node")
    graph.add_edge("patch_applier_node", "pytest_validation_node")

    graph.add_conditional_edges(
        "pytest_validation_node",
        route_after_validation,
        {
            "ast_scanner_node": "ast_scanner_node",
            END: END
        }
    )

    return graph.compile()


def create_initial_state(repository_path: str, max_retries: int = 3) -> RefactorState:
    """Create initial state for the refactoring engine."""
    return {
        "repository_path": repository_path,
        "modules_to_refactor": [],
        "ast_dependency_map": {},
        "file_patches": {},
        "test_results": {},
        "retry_count": 0,
        "max_retries": max_retries
    }