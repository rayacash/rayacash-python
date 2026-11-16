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
    identity = README[README.index("## Identidad\n") : README.index("## Raya PSP\n")]
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


PSP_ERROR_CODES = (
    "PSP_NOT_ACTIVATED",
    "CUSTOMER_NOT_FOUND",
    "CUSTOMER_ALREADY_EXISTS",
    "CUSTOMER_STATUS_CONFLICT",
    "CUSTOMER_INSUFFICIENT_BALANCE",
    "CUSTOMER_DATA_MISMATCH",
    "TAX_ID_NOT_REGISTERED",
)
PSP_EVENT_TYPES = (
    "psp.customer.activated",
    "psp.customer.updated",
    "psp.customer.failed",
    "psp.customer.rejected",
    "psp.customer.blocked",
    "psp.customer.unblocked",
    "psp.customer.closed",
    "psp.transfer.received",
    "psp.transfer.sent",
    "psp.transfer.failed",
    "psp.document_request.created",
    "psp.document_request.closed",
)


def test_the_readme_covers_raya_psp() -> None:
    # Va entre «Identidad» y «Errores», con su entrada en el índice.
    contents = README[README.index("## Contenido\n") : README.index("## Antes de empezar\n")]
    assert "- [Identidad](#identidad)\n- [Raya PSP](#raya-psp)\n- [Errores](#errores)\n" in contents
    assert (
        README.index("\n## Identidad\n")
        < README.index("\n## Raya PSP\n")
        < README.index("\n## Errores\n")
    )
    psp = README[README.index("## Raya PSP\n") : README.index("## Errores\n")]
    assert "https://raya.cash/api/psp" in psp
    assert "`client.psp` existe desde la 1.3.0." in psp
    # El flujo, en orden: crear → activated → retrieve → transferir → received → bloquear → listar.
    flow = [
        "psp.customers.create(",
        "`psp.customer.activated`",
        "psp.customers.retrieve(",
        "psp.transfers.create(",
        "`psp.transfer.received`",
        "psp.customers.block(",
        "psp.customers.list(",
    ]
    positions = [psp.index(step) for step in flow]
    assert positions == sorted(positions)
    for step in ("psp.customers.create(", "psp.transfers.create(", "psp.customers.block("):
        assert any(step in block for block in BLOCKS), step
    # La tabla con los 12 métodos.
    for method in (
        "create",
        "retrieve",
        "list",
        "retrieve_balance",
        "block",
        "unblock",
        "close",
        "recreate",
    ):
        assert f"| `client.psp.customers.{method}(" in psp, method
    for method in ("create", "retrieve", "list"):
        assert f"| `client.psp.transfers.{method}(" in psp, method
    assert "| `client.psp.balance.retrieve(" in psp
    # Tu saldo manda: primero el tuyo, después el de tu cliente.
    assert "**Tu saldo manda.**" in psp
    assert psp.index("`INSUFFICIENT_BALANCE`") < psp.index("`CUSTOMER_INSUFFICIENT_BALANCE`")
    # Las formas de crear un cliente y el 202; sin la activación, PSP_NOT_ACTIVATED; sin sandbox.
    for text in (
        "**Con Identidad:**",
        "**Con las fotos:**",
        "`202`",
        'code == "PSP_NOT_ACTIVATED"',
        "`SANDBOX_NOT_SUPPORTED`",
    ):
        assert text in psp, text
    for code in PSP_ERROR_CODES:
        assert f"`{code}`" in psp, code
    errors = README[README.index("## Errores\n") : README.index("## Webhooks\n")]
    for code in PSP_ERROR_CODES:
        assert f"`{code}`" in errors, code
    webhooks = README[README.index("## Webhooks\n") : README.index("## Sandbox\n")]
    for event_type in PSP_EVENT_TYPES:
        assert f"`{event_type}`" in webhooks, event_type
    sandbox = README[
        README.index("\n## Sandbox\n") : README.index("\n## Tests de tu integración\n")
    ]
    assert "Raya PSP (`client.psp`)" in sandbox
    # Sin términos (la API no los recibe), sin precios y sin hablar por el regulador.
    assert "terms_accepted_at" not in README
    assert not re.search(r"\$\s?\d|\bARS\s?\d|\bUSD\s?\d", psp)
    assert not re.search(r"autorizad[oa]s?\b|regulad[oa]s? por", psp, flags=re.IGNORECASE)


def test_the_readme_creates_psp_customers_in_three_forms() -> None:
    # Enmienda A7: con Identidad alcanza identity_verification; sin ella, los datos (y las fotos de
    # una persona humana). Sin gender en ningún lado: el sexo sale de la verificación o del DNI.
    psp = README[README.index("## Raya PSP\n") : README.index("## Errores\n")]
    first = next(block for block in BLOCKS if "psp.customers.create(" in block)
    call = first[first.index("psp.customers.create(") : first.index("\n)\n")]
    assert 'identity_verification="idv_' in call
    for name in ("tax_id=", "name=", "person_type=", "_url="):
        assert name not in call, name
    for text in (
        "**Qué mandar para crearlo.**",
        "**Con Identidad:**",
        "**Con las fotos:**",
        "**Una persona jurídica:**",
        "con ella no mandes `tax_id`, `name`, `person_type` ni fotos",
        "con tu propio KYC o con otro proveedor",
        "`@overload`",
    ):
        assert text in psp, text
    assert not re.search("gender", README, flags=re.IGNORECASE)
    # La tabla, con la firma de la implementación: todo opcional, en el orden de la API.
    assert (
        "| `client.psp.customers.create(*, identity_verification=None, tax_id=None, name=None, "
        "person_type=None, document_front_url=None, document_back_url=None, selfie_url=None, "
        "external_reference=None, metadata=None, idempotency_key=None, options=None)` | "
        "`POST /v1/psp/customers` |"
    ) in psp
    # CUSTOMER_DATA_MISMATCH queda para la razón social de una persona jurídica, y
    # CUSTOMER_ALREADY_EXISTS también es una verificación que ya usaste.
    errors = README[README.index("## Errores\n") : README.index("## Webhooks\n")]
    for section in (psp, errors):
        assert "ya usaste esa verificación de Identidad para otro" in section
        assert "`tax_id` o `name`" not in section
    assert "`CUSTOMER_DATA_MISMATCH` (solo una persona jurídica" in psp
    assert "`CUSTOMER_DATA_MISMATCH`: la razón social de una persona jurídica" in errors


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
