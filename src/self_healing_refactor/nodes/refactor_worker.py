from pathlib import Path
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..state.schemas import ModuleState
from ..utils.llm_prompts import REFACTOR_SYSTEM_PROMPT, REFACTOR_USER_PROMPT_TEMPLATE


def parallel_refactor_worker(state: ModuleState) -> Dict[str, Dict[str, str]]:
    """Refactor a single module using LLM, incorporating test failure feedback."""
    module_path = state["module_path"]
    repository_path = state["repository_path"]
    test_results = state.get("test_results", {})

    full_path = Path(repository_path) / module_path
    if not full_path.exists():
        return {"file_patches": {}}

    with open(full_path, "r", encoding="utf-8") as f:
        original_code = f.read()

    relevant_failures = []
    for test_file, result in test_results.items():
        if result.get("failed", False):
            traceback = result.get("traceback", "")
            module_name = ".".join(Path(module_path).with_suffix("").parts)
            if module_name in traceback:
                relevant_failures.append({
                    "test_file": test_file,
                    "traceback": traceback,
                    "error": result.get("error", "")
                })

    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)

    system_msg = SystemMessage(content=REFACTOR_SYSTEM_PROMPT)
    user_msg = HumanMessage(content=REFACTOR_USER_PROMPT_TEMPLATE.format(
        module_path=module_path,
        original_code=original_code,
        test_failures=relevant_failures if relevant_failures else "No specific test failures for this module."
    ))

    response = llm.invoke([system_msg, user_msg])
    refactored_code = response.content.strip()

    if refactored_code.startswith("```python"):
        refactored_code = refactored_code[9:]
    if refactored_code.endswith("```"):
        refactored_code = refactored_code[:-3]
    refactored_code = refactored_code.strip()

    if refactored_code != original_code:
        return {"file_patches": {module_path: refactored_code}}
    return {"file_patches": {}}