from typing import Literal
from langgraph.graph import END

from ..state.schemas import RefactorState


def should_continue_refactoring(state: RefactorState) -> Literal["continue", "success", "max_retries"]:
    """Determine the next step based on test results and retry count."""
    test_results = state.get("test_results", {})
    return_code = test_results.get("return_code", 1)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if return_code == 0:
        return "success"
    elif retry_count >= max_retries:
        return "max_retries"
    else:
        return "continue"


def route_after_validation(state: RefactorState) -> str:
    """Route to appropriate next node after pytest validation."""
    decision = should_continue_refactoring(state)

    if decision == "success":
        return END
    elif decision == "max_retries":
        return END
    else:
        return "ast_scanner_node"