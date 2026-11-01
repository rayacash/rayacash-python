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
