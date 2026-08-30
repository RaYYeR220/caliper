"""The one-way dependency, checked rather than asserted.

`README.md`, `EVIDENCE.md`, `JUDGES.md` and `AGENTS.md` all make the same claim: the modules that
produce a screening verdict — `caliper/evaluate.py` and `caliper/screen.py` — have no import path to
`caliper/agents/` or `caliper/llm/`. It is the central design claim of the project. A model compiles
the criteria and writes the prose; it does not decide who is eligible, and the reason that is a fact
rather than a promise is that the code which decides cannot reach the code which calls a provider.

Three things make this test hard to fool, and each corresponds to a way the claim could quietly stop
being true:

*Transitivity.* Reading the top of the two files proves nothing. `evaluate.py` imports `ir.py`, and
one `from caliper.agents.critic import ...` in `ir.py` would put a model call one attribute access
away from a verdict while leaving both files looking clean. So the whole closure is walked.

*Position in the file.* `ast.walk` descends into function bodies, class bodies and `if
TYPE_CHECKING:` blocks, so an import hidden inside a function — the usual way a cycle gets broken
under deadline — is caught in the same pass as one at the top. A `TYPE_CHECKING` import is caught
too. It is invisible at runtime, but it is a dependency a reader has to follow and a refactor will
eventually make real, and the claim is about the design rather than about what the interpreter
happens to execute.

*Spelling.* A name can be assembled at run time and handed to `importlib.import_module`, which no
import statement records. Constant-string dynamic imports are read like any other import, and a
dynamic import with a computed name is refused outright inside this closure: there is no legitimate
use for one here, and allowing it would leave exactly one hole in the wall.

`tests/test_metamorphic.py` makes the matching check for `eval/metamorphic/`, which is a different
claim about a different tree. This file is the one behind the sentence in the documents.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
PACKAGE_ROOT = SOURCE_ROOT / "caliper"

ENTRY_POINTS = ("caliper.evaluate", "caliper.screen")

# The model runtime, and the transports it would need. `caliper.agents` and `caliper.llm` are the
# claim itself; the rest are there because importing `openai` directly from the evaluator would
# break the claim in spirit while leaving both named packages untouched.
FORBIDDEN_ROOTS = (
    "caliper.agents",
    "caliper.llm",
    "openai",
    "httpx",
    "requests",
    "socket",
    "urllib.request",
)

_DYNAMIC_IMPORT_NAMES = ("import_module", "__import__")


def _module_files() -> dict[str, Path]:
    """Every module in the installed package, by its dotted name."""
    modules: dict[str, Path] = {}
    for path in PACKAGE_ROOT.rglob("*.py"):
        parts = path.relative_to(SOURCE_ROOT).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path
    return modules


def _absolute(node: ast.ImportFrom, module_name: str) -> str | None:
    """The module a `from ... import ...` names, resolving a relative one against its own package.

    There are no relative imports in this package today. Resolving them anyway is the point: a
    future `from .agents.critic import review` must not slip past a check that only understands
    absolute names.
    """
    if not node.level:
        return node.module
    package = module_name.split(".")
    # A module's own package is its name minus the module; a package's own package is itself.
    if _module_files().get(module_name, PACKAGE_ROOT).name != "__init__.py":
        package = package[:-1]
    base = package[: len(package) - (node.level - 1)] if node.level > 1 else package
    if not base:
        return node.module
    return ".".join([*base, node.module]) if node.module else ".".join(base)


def _imported_names(path: Path, module_name: str) -> set[str]:
    """Every module name this file imports, wherever in the file and however it is spelled.

    `ast.walk` visits the whole tree, so a `def` body, a class body and an `if TYPE_CHECKING:` block
    are read exactly like the top of the file.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _absolute(node, module_name)
            if resolved is None:
                continue
            names.add(resolved)
            # `from caliper.llm import client` names a module; `from caliper.ir import Code` names
            # an attribute. Both spellings are recorded and the resolver sorts out which is which.
            names.update(f"{resolved}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call):
            names.update(_dynamic_import_target(node))
    return names


def _dynamic_import_target(node: ast.Call) -> set[str]:
    """The module a constant-string `import_module` or `__import__` call would load."""
    if _called_name(node.func) not in _DYNAMIC_IMPORT_NAMES:
        return set()
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return {node.args[0].value}
    return set()


def _called_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _computed_dynamic_imports(tree: ast.AST) -> list[str]:
    """Dynamic imports whose target is not a literal, and so cannot be read by this test."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node.func)
        if name not in _DYNAMIC_IMPORT_NAMES:
            continue
        first = node.args[0] if node.args else None
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            found.append(name)
    return found


def _resolve(name: str, modules: dict[str, Path]) -> str | None:
    """The module an imported name belongs to, dropping a trailing attribute if there is one."""
    if name in modules:
        return name
    parent = name.rpartition(".")[0]
    return parent if parent in modules else None


def import_closure(*entry_points: str) -> dict[str, set[str]]:
    """Every module reachable from these entry points, with what each one imports.

    Only edges inside `caliper` are followed: what `pydantic` imports is not this project's claim to
    make. Names outside the package are still recorded against the module that imported them, which
    is how a direct `import openai` is caught.
    """
    modules = _module_files()
    edges: dict[str, set[str]] = {}
    pending = list(entry_points)
    while pending:
        current = pending.pop()
        if current in edges:
            continue
        path = modules.get(current)
        assert path is not None, f"{current} is not a module in {PACKAGE_ROOT}"
        imported = _imported_names(path, current)
        edges[current] = imported
        for name in imported:
            resolved = _resolve(name, modules)
            if resolved is not None and resolved not in edges:
                pending.append(resolved)
    return edges


def _offending(name: str) -> str | None:
    for root in FORBIDDEN_ROOTS:
        if name == root or name.startswith(f"{root}."):
            return root
    return None


# ------------------------------------------------------------------------------------------------
# The claim
# ------------------------------------------------------------------------------------------------


def test_the_verdict_cannot_reach_a_model() -> None:
    """`evaluate.py` and `screen.py`, and everything they transitively import, are model-free."""
    edges = import_closure(*ENTRY_POINTS)
    violations = sorted(
        f"{module} imports {name}"
        for module, imported in edges.items()
        for name in imported
        if _offending(name) is not None
    )
    assert not violations, (
        "the screening verdict has an import path to the model runtime:\n  "
        + "\n  ".join(violations)
    )


def test_the_closure_is_the_one_the_documents_describe() -> None:
    """A walker that silently followed nothing would pass the check above by doing no work.

    This is the guard on the guard. The closure is small and stable, and naming it here means a
    refactor that pulls a new module under the evaluator has to be looked at rather than absorbed.
    """
    assert set(import_closure(*ENTRY_POINTS)) == {
        "caliper.evaluate",
        "caliper.screen",
        "caliper.ir",
        "caliper.logic",
        "caliper.record",
        "caliper.settlements",
        "caliper.units",
    }


@pytest.mark.parametrize("module", sorted(import_closure(*ENTRY_POINTS)))
def test_no_module_in_the_closure_imports_by_a_computed_name(module: str) -> None:
    """A name assembled at run time is an import this file cannot read, so it is not allowed."""
    path = _module_files()[module]
    computed = _computed_dynamic_imports(ast.parse(path.read_text(encoding="utf-8")))
    assert not computed, f"{module} calls {computed} with a name this check cannot follow"


# ------------------------------------------------------------------------------------------------
# The scanner, checked against imports written the ways that hide
# ------------------------------------------------------------------------------------------------


HIDDEN_IMPORTS = '''
"""A module that reaches the model runtime in every way except the obvious one."""

from typing import TYPE_CHECKING

import importlib

if TYPE_CHECKING:
    from caliper.agents.critic import CriticReport


def evaluate(criteria):
    from caliper.llm import LLMClient  # a cycle broken under deadline

    return LLMClient, importlib.import_module("caliper.agents.compiler")
'''


@pytest.mark.parametrize(
    "expected",
    ["caliper.agents.critic", "caliper.llm", "caliper.agents.compiler"],
    ids=["type-checking", "function-local", "dynamic"],
)
def test_the_scanner_reads_imports_that_are_not_at_the_top_of_the_file(
    tmp_path: Path, expected: str
) -> None:
    """Written as a fixture rather than asserted: a scanner nobody has seen fail proves nothing."""
    source = tmp_path / "hidden.py"
    source.write_text(HIDDEN_IMPORTS, encoding="utf-8")

    names = _imported_names(source, "caliper.hidden")

    assert expected in names
    assert _offending(expected) is not None


def test_a_relative_import_resolves_to_the_package_it_names(tmp_path: Path) -> None:
    """No module uses one today, which is exactly why the resolver has to be exercised here."""
    source = tmp_path / "relative.py"
    source.write_text("from .agents.critic import review\n", encoding="utf-8")

    names = _imported_names(source, "caliper.evaluate")

    assert "caliper.agents.critic" in names
    assert _offending("caliper.agents.critic") is not None


def test_an_import_of_a_module_is_told_apart_from_an_import_of_a_name() -> None:
    modules = _module_files()
    assert _resolve("caliper.ir", modules) == "caliper.ir"
    assert _resolve("caliper.ir.CriteriaSet", modules) == "caliper.ir"
    assert _resolve("pydantic", modules) is None
