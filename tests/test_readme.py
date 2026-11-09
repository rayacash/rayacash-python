"""Los ejemplos del README y de examples/ tienen que compilar (y algunos, correr)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
BLOCKS = re.findall(r"```python\n(.*?)```", README, flags=re.DOTALL)


def test_the_readme_has_python_examples() -> None:
    assert len(BLOCKS) >= 10


@pytest.mark.parametrize("index", range(len(BLOCKS)))
def test_readme_blocks_compile(index: int) -> None:
    compile(
        BLOCKS[index], f"README.md#bloque-{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    )


def test_the_readme_covers_apps_and_connected_accounts() -> None:
    assert "## Apps y cuentas conectadas" in README
    assert any("client.oauth.token(" in block for block in BLOCKS)
    assert any("checkout.orders.create(" in block for block in BLOCKS)
    assert any("users.retrieve(" in block for block in BLOCKS)


def test_the_docstrings_say_we_for_webhook_destinations() -> None:
    # Los destinos de Developers › Webhooks son ``we_…`` (``whe_`` fue el prefijo de un borrador).
    sources = sorted((ROOT / "src" / "rayacash").glob("*.py"))
    assert sources
    for path in sources:
        assert "whe_" not in path.read_text(encoding="utf-8"), path.name
    assert "whe_" not in README


def test_the_offline_testing_example_runs() -> None:
    (block,) = [b for b in BLOCKS if "httpx.MockTransport" in b]
    exec(compile(block, "README.md", "exec"), {})  # no sale a la red: usa MockTransport


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "examples").glob("*.py")) + sorted((ROOT / "scripts").glob("*.py")),
    ids=lambda path: path.name,
)
def test_examples_compile(path: Path) -> None:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
