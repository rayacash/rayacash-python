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


def _import_header(block: str) -> list[str]:
    """Los imports del principio de un ejemplo (hasta la primera línea de código)."""
    lines = block.split("\n")
    first = next((i for i, line in enumerate(lines) if re.match(r"(import|from)\s", line)), None)
    if first is None:
        return []
    header: list[str] = []
    for line in lines[first:]:
        if re.match(r"(import|from)\s", line) or not line.strip():
            header.append(line)
        else:
            break
    while header and not header[-1].strip():
        header.pop()
    return header


@pytest.mark.parametrize("index", range(len(BLOCKS)))
def test_the_imports_of_each_example_go_together(index: int) -> None:
    # Como en la doc web (/api): un solo bloque de imports, sin las líneas en blanco entre
    # secciones que dejaría isort.
    header = _import_header(BLOCKS[index])
    assert all(line.strip() for line in header), "\n".join(header)


def test_the_readme_covers_raya_connect() -> None:
    assert "## Raya Connect" in README
    assert any("client.oauth.token(" in block for block in BLOCKS)
    assert any("connect.orders.create(" in block for block in BLOCKS)
    assert any("users.retrieve(" in block for block in BLOCKS)
    assert "**4. Creá pagos a su nombre** con `connect.orders` (desde la 1.2.0)." in README
    assert "`connect.payouts`" in README
    assert any("connect.payouts.create(" in block for block in BLOCKS)
    assert any("connect.payouts.list(" in block for block in BLOCKS)
    # Los payouts van con la clave secreta, a diferencia de users y connect.orders.
    assert "Los payouts **van con tu clave secreta**" in README
    assert "`PAYOUT_ORIGIN_UNAVAILABLE`" in README
    assert "`PAYOUT_NOT_FOUND`" in README


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
    connect = README[README.index("## Raya Connect\n") : README.index("## Identidad\n")]
    assert connect.rstrip().endswith(line)
    # Antes, en el mismo párrafo, desde qué versión existe cada nombre (como en los otros SDKs).
    since = (
        "`client.oauth` y `client.users` existen desde la 1.1.0, y `client.connect` y "
        "`rayacash.ConnectOrder`, desde la 1.2.0. "
    )
    assert connect.rstrip().endswith("\n\n" + since + line)
    # Siempre «desde la 1.x.0», con «la».
    assert not re.search(r"desde \d", README)


def test_the_readme_covers_identity() -> None:
    # Crear → url o Identity.js → webhook → retrieve con person → files → cancel → list.
    assert "- [Identidad](#identidad)" in README
    identity = README[README.index("## Identidad\n") : README.index("## Errores\n")]
    assert "https://raya.cash/api/identity" in identity
    assert "`npm install rayacash-identity`" in identity
    assert 'import { RayaIdentity } from "rayacash-identity";' in identity
    for method in ("create", "retrieve", "files", "cancel", "list"):
        assert any(f"identity.verifications.{method}(" in block for block in BLOCKS), method
        assert f"| `client.identity.verifications.{method}(" in identity, method
    for event_type in ("verified", "declined", "expired", "canceled"):
        assert f"`identity.verification.{event_type}`" in identity
        assert f"`identity.verification.{event_type}`" in README[README.index("## Webhooks\n") :]
    for code in (
        "VERIFICATION_NOT_FOUND",
        "VERIFICATION_NOT_CANCELABLE",
        "SANDBOX_NOT_SUPPORTED",
        "IDENTITY_NOT_ACTIVATED",
    ):
        assert f"`{code}`" in README[README.index("## Errores\n") :], code
    assert 'person.document["copy"]' in identity  # document.copy es dict.copy()
    # Identity.js va por npm (primero) o con el <script> del CDN de Raya, sin ninguna clave:
    # nunca por un CDN de terceros ni copiado a los estáticos del sitio. Del CDN, solo el
    # origen (en la CSP), v1 (la última 1.x) o una versión fija.
    script = '<script src="https://cdn.raya.cash/identity/v1/identity.js"></script>'
    assert identity.index("`npm install rayacash-identity`") < identity.index(script)
    assert "`frame-src https://raya.cash`" in identity
    assert "`https://cdn.raya.cash` a `script-src`" in identity
    for url in re.findall(r"https?://js\.raya\.cash[^\s\"'`)<>]*", README):
        assert re.fullmatch(
            r"https://js\.raya\.cash(/identity/v(1|\d+\.\d+\.\d+)/identity\.js)?", url
        ), url
    assert not re.search(r"unpkg|jsdelivr|esm\.sh|skypack|cdnjs", README, flags=re.IGNORECASE)
    assert not re.search(
        r"archivos estáticos|tus estáticos|node_modules/rayacash-identity/dist", README
    )
    scripts = re.findall(r"```js\n(.*?)```", README, flags=re.DOTALL)
    assert scripts
    for script in scripts:
        assert "raya_sk_" not in script
        assert "RAYA_SECRET_KEY" not in script
    # Sin precios.
    assert not re.search(r"\$\s?\d|\bARS\s?\d", identity)


def test_the_readme_covers_the_sandbox() -> None:
    # «Sandbox» va después de «Webhooks», condicionada a que la cuenta lo tenga: las guías para IA
    # salen de este README y el sandbox puede no estar abierto para todas las cuentas.
    contents = README[README.index("## Contenido\n") : README.index("## Antes de empezar\n")]
    assert "- [Webhooks](#webhooks)\n- [Sandbox](#sandbox)\n- [Tests de tu" in contents
    sandbox = README[
        README.index("\n## Sandbox\n") : README.index("\n## Tests de tu integración\n")
    ]
    assert README.index("\n## Webhooks\n") < README.index("\n## Sandbox\n")
    assert (
        "Si en el menú de tu perfil del dashboard aparece «Crear sandbox» o «Sandboxes», tu cuenta "
        "ya lo tiene"
    ) in sandbox
    assert "Si no aparece, tu cuenta todavía no lo tiene." in sandbox
    assert any("test_helpers.payments.simulate_transfer(" in block for block in BLOCKS)
    assert (
        "| `client.test_helpers.payments.simulate_transfer(payment_id, *, amount=None, "
        "options=None)` | `POST /v1/test/payments/:id/simulate_transfer` |"
    ) in sandbox
    for text in (
        "`raya_sk_test_…`",
        "`raya_pk_test_…`",
        "`raya_at_test_…`",
        "`raya_cs_test_…`",
        "`event.livemode`",
        "`rayacash.Payment.simulate_transfer(...)`",
        'code == "SANDBOX_NOT_SUPPORTED"',
        # Un evento sale solo hacia los destinos que ya existían cuando ocurrió.
        "antes de simular",
        "después de crearlo",
        # Al pasar a la cuenta real cambian la clave y el secreto del destino.
        "`RAYA_WEBHOOK_SECRET`",
        # Una orden simulada vuelve ligada al cliente de la clave secreta: el refund va con el
        # del access_token.
        "connected.connect.orders.refund(...)",
        'code == "ACCESS_TOKEN_INVALID"',
    ):
        assert text in sandbox, text
    # Los límites de reembolso del sandbox son los de la cuenta: no son «más bajos».
    assert "más bajos" not in sandbox
    # livemode puede faltar en un evento viejo: siempre con get, nunca por atributo.
    webhooks = README[README.index("## Webhooks\n") : README.index("## Sandbox\n")]
    assert 'leelo siempre con `event.get("livemode", True)`' in webhooks
    errors = README[README.index("## Errores\n") : README.index("## Webhooks\n")]
    for code in ("SANDBOX_NOT_SUPPORTED", "SANDBOX_ONLY", "PAYMENT_NOT_PENDING"):
        assert f"`{code}`" in errors, code
    # Lo que reemplazó el sandbox (las apps tenían una cuenta para probar) no vuelve a aparecer. Las
    # frases van armadas, así el grep de los términos retirados sigue limpio en el repo.
    retired = [
        "modo de " + "prueba",
        "modo " + "test",
        "test " + "mode",
        "cuenta de " + "prueba",
        "probar sin cuentas " + "reales",
        "› " + r"test\b",
    ]
    assert not re.search("|".join(retired), README, flags=re.IGNORECASE)


def test_the_docstrings_say_we_for_webhook_destinations() -> None:
    # Los destinos de Developers › Webhooks son ``we_…`` (``whe_`` fue el prefijo de un borrador).
    sources = sorted((ROOT / "src" / "rayacash").glob("*.py"))
    assert sources
    for path in sources:
        assert "whe_" not in path.read_text(encoding="utf-8"), path.name
    assert "whe_" not in README


def test_the_sources_do_not_name_other_providers() -> None:
    # Los docstrings y comentarios salen con el paquete (help(rayacash), el editor). El nombre
    # va armado, así el grep del repo sigue limpio.
    competitor = "str" + "ipe"
    sources = sorted((ROOT / "src" / "rayacash").glob("*.py"))
    assert sources
    for path in sources:
        assert competitor not in path.read_text(encoding="utf-8").lower(), path.name
    assert competitor not in README.lower()


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
