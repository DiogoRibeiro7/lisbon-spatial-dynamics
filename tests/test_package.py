"""Basic package import test."""

import ast
from importlib import import_module
from pathlib import Path
from typing import TypeGuard

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "lisbon_spatial_dynamics"


def test_package_imports() -> None:
    """The package should be importable."""
    module = import_module("lisbon_spatial_dynamics")
    assert module is not None


def _imports_pyplot(node: ast.AST) -> TypeGuard[ast.Import | ast.ImportFrom]:
    if isinstance(node, ast.Import):
        return any(alias.name == "matplotlib.pyplot" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module == "matplotlib.pyplot" or (
            node.module == "matplotlib" and any(alias.name == "pyplot" for alias in node.names)
        )
    return False


def test_figures_render_without_pyplot() -> None:
    """Figure writers must not depend on pyplot's GUI backend or global figure state.

    On desktops with Tk installed, pyplot selects an interactive backend and creates
    a Tk interpreter per figure, which fails intermittently while writing PNGs.
    """
    offenders = sorted(
        f"{path.relative_to(PACKAGE_ROOT)}:{node.lineno}"
        for path in PACKAGE_ROOT.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if _imports_pyplot(node)
    )
    assert offenders == [], "use matplotlib.figure.Figure instead of pyplot: " + ", ".join(
        offenders
    )
