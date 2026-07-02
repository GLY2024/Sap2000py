"""Static guardrails for the public handle API."""

from __future__ import annotations

import ast
from pathlib import Path


def test_src_does_not_call_as_name_outside_handles_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "sap2000py"
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        if path.name == "handles.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "as_name"
            ):
                offenders.append(f"{path.relative_to(root)}:{node.lineno}")

    assert offenders == []
