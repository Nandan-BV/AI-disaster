import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Set

from ..state.schemas import RefactorState


class ModuleVisitor(ast.NodeVisitor):
    """AST visitor to extract imports and module dependencies."""

    def __init__(self, module_path: str, repository_root: Path):
        self.module_path = module_path
        self.repository_root = repository_root
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, List[str]] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            if node.module not in self.from_imports:
                self.from_imports[node.module] = []
            for alias in node.names:
                self.from_imports[node.module].append(alias.name)
        self.generic_visit(node)


def resolve_module_path(import_name: str, repository_root: Path, current_module_dir: Path) -> str | None:
    """Resolve an import name to a file path within the repository."""
    parts = import_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        candidate_path = repository_root / candidate.replace(".", "/")
        if candidate_path.with_suffix(".py").exists():
            return str(candidate_path.with_suffix(".py").relative_to(repository_root))
        if (candidate_path / "__init__.py").exists():
            return str(candidate_path.relative_to(repository_root))
    return None


def build_dependency_map(repository_path: str) -> Dict[str, List[str]]:
    """Build a module dependency map by scanning Python files."""
    repo_root = Path(repository_path).resolve()
    dependency_map: Dict[str, List[str]] = {}
    python_files: List[Path] = []

    for py_file in repo_root.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            python_files.append(py_file)

    for py_file in python_files:
        relative_path = str(py_file.relative_to(repo_root))
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=relative_path)
        except (SyntaxError, UnicodeDecodeError):
            continue

        visitor = ModuleVisitor(relative_path, repo_root)
        visitor.visit(tree)

        dependencies: List[str] = []
        for imp in visitor.imports:
            resolved = resolve_module_path(imp, repo_root, py_file.parent)
            if resolved:
                dependencies.append(resolved)

        for mod, names in visitor.from_imports.items():
            resolved = resolve_module_path(mod, repo_root, py_file.parent)
            if resolved:
                dependencies.append(resolved)

        dependency_map[relative_path] = dependencies

    return dependency_map


def get_modules_to_refactor(dependency_map: Dict[str, List[str]], test_results: Dict[str, Any]) -> List[str]:
    """Determine which modules need refactoring based on test failures."""
    failed_modules: Set[str] = set()

    for test_file, result in test_results.items():
        if result.get("failed", False):
            traceback = result.get("traceback", "")
            for module in dependency_map:
                if module.replace("/", ".").replace(".py", "") in traceback:
                    failed_modules.add(module)

    if not failed_modules:
        return list(dependency_map.keys())

    return list(failed_modules)


def ast_scanner_node(state: RefactorState) -> RefactorState:
    """Scan repository, build AST dependency map, and identify modules to refactor."""
    repository_path = state["repository_path"]

    dependency_map = build_dependency_map(repository_path)
    modules_to_refactor = get_modules_to_refactor(dependency_map, state.get("test_results", {}))

    return {
        **state,
        "ast_dependency_map": dependency_map,
        "modules_to_refactor": modules_to_refactor,
        "retry_count": state.get("retry_count", 0) + 1,
    }