# Self-Healing Codebase Refactoring Engine

A production-grade Python application using LangGraph (StateGraph), LangChain, Python AST, and PyTest to automatically refactor and fix codebases.

## Architecture

```
START → ast_scanner_node 
  → [Send() × modules_to_refactor] → parallel_refactor_worker (map)
  → patch_applier_node (reduce)
  → pytest_validation_node
  → {0: END, ≠0 & retry<max: ast_scanner_node, ≠0 & retry≥max: END}
```

## Components

- **AST Scanner** (`nodes/ast_scanner.py`): Scans repository, builds import dependency maps using Python's `ast` module
- **Parallel Refactor Worker** (`nodes/refactor_worker.py`): Maps across modules, uses LLM to refactor with test failure context
- **Patch Applier** (`nodes/patch_applier.py`): Writes aggregated patches to disk
- **Pytest Validator** (`nodes/pytest_validator.py`): Runs pytest, captures results and tracebacks
- **Routing Logic** (`graph/routing.py`): Conditional edges for retry loop

## Installation

```bash
pip install -r requirements.txt
```

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-key-here"
```

## Usage

```bash
# Run on test project
python -m src.self_healing_refactor test_project --max-retries 3

# Or with API key
python -m src.self_healing_refactor test_project --api-key "your-key"
```

## Project Structure

```
src/self_healing_refactor/
├── __init__.py
├── main.py                    # CLI entrypoint
├── state/
│   ├── __init__.py
│   └── schemas.py             # RefactorState, ModuleState
├── nodes/
│   ├── __init__.py
│   ├── ast_scanner.py         # AST-based dependency scanning
│   ├── refactor_worker.py     # LLM-based refactoring
│   ├── patch_applier.py       # Write patches to disk
│   └── pytest_validator.py    # Run pytest, capture results
├── graph/
│   ├── __init__.py
│   ├── builder.py             # StateGraph assembly
│   └── routing.py             # Conditional edge logic
└── utils/
    ├── __init__.py
    └── llm_prompts.py         # LLM prompt templates

test_project/                   # Example project with bugs
├── mypackage/
│   ├── __init__.py
│   ├── calculator.py          # Has bugs in add/subtract
│   └── string_utils.py        # Has bugs in reverse/capitalize
└── tests/
    ├── test_calculator.py
    └── test_string_utils.py
```

## How It Works

1. **Scan**: AST scanner builds module dependency graph
2. **Identify**: Determines which modules need refactoring based on test failures
3. **Refactor**: Parallel LLM workers refactor each module with failure context
4. **Apply**: Patches written to disk
5. **Validate**: Pytest runs, results captured
6. **Loop**: On failure, retry with new context (up to max_retries)

## Requirements

- Python 3.10+
- OpenAI API key (for GPT-4)
- langgraph, langchain, langchain-openai
- pytest, pytest-json-report