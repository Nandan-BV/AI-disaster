from langgraph.graph import END

from src.self_healing_refactor.graph.routing import (
    route_after_validation,
    should_continue_refactoring,
)


def test_validation_routes_back_to_scanner_until_retry_limit():
    state = {
        "test_results": {"return_code": 1},
        "retry_count": 1,
        "max_retries": 3,
    }

    assert should_continue_refactoring(state) == "continue"
    assert route_after_validation(state) == "ast_scanner_node"


def test_validation_stops_after_max_retries():
    state = {
        "test_results": {"return_code": 1},
        "retry_count": 3,
        "max_retries": 3,
    }

    assert should_continue_refactoring(state) == "max_retries"
    assert route_after_validation(state) == END


def test_validation_stops_on_success_even_at_retry_limit():
    state = {
        "test_results": {"return_code": 0},
        "retry_count": 3,
        "max_retries": 3,
    }

    assert should_continue_refactoring(state) == "success"
    assert route_after_validation(state) == END
