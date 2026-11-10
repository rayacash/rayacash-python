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


def test_the_readme_covers_raya_connect() -> None:
    assert "## Raya Connect" in README
    assert any("client.oauth.token(" in block for block in BLOCKS)
    assert any("connect.orders.create(" in block for block in BLOCKS)
    assert any("users.retrieve(" in block for block in BLOCKS)
    assert "**4. Creá pagos a su nombre** con `connect.orders` (desde la 1.2.0)." in README


def test_the_readme_uses_the_new_names_and_one_line_for_1_1_0() -> None:
    # Los ejemplos usan solo los nombres de Raya Connect; los de la 1.1.0 (alias deprecados) van en
    # una sola línea, al final de la sección. Las guías para IA salen de este README.
    for block in BLOCKS:
        assert "checkout.orders" not in block
        assert "checkout_id" not in block
        assert not re.search(r"\bCheckout(Status)?\b", block)
    line = (
        "Si venís de la 1.1.0: `client.checkout.orders` y `rayacash.Checkout` siguen andando como "
        "alias deprecados (con un `DeprecationWarning`) hasta la 2.0.0; en código nuevo usá los "
        "nombres de arriba."
    )
    assert README.count(line) == 1
    assert README.count("checkout.orders") == README.count("rayacash.Checkout") == 1
    connect = README[README.index("## Raya Connect\n") : README.index("## Errores\n")]
    assert connect.rstrip().endswith(line)
    # Antes, en el mismo párrafo, desde qué versión existe cada nombre (como en los otros SDKs).
    since = (
        "`client.oauth` y `client.users` existen desde la 1.1.0, y `client.connect` y "
        "`rayacash.ConnectOrder`, desde la 1.2.0. "
    )
    assert connect.rstrip().endswith("\n\n" + since + line)
    # Siempre «desde la 1.x.0», con «la».
    assert not re.search(r"desde \d", README)


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
