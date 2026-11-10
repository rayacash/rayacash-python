"""Los nombres de la 1.1.0 que la 1.2.0 cambió por los de Raya Connect: alias deprecados.

Cada alias es el mismo objeto que su nombre nuevo, llama a las rutas nuevas (/v1/connect/orders)
y avisa con un DeprecationWarning que apunta a la línea de quien lo usa. Se van en la 2.0.0.
"""

from __future__ import annotations

import ast
import contextlib
import json
import pickle
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from typing_extensions import get_args

import rayacash
from rayacash._deprecated import deprecation_message
from rayacash._object_classes import OBJECT_CLASSES
from rayacash._raya_object import convert_to_raya_object
from tests import helpers
from tests.fixtures import WEBHOOK_SECRET
from tests.fixtures_apps import (
    ACCESS_TOKEN,
    EVENT_ORDER_SUCCEEDED,
    ORDER_ID,
    ORDER_PENDING,
    ORDER_REFUNDED,
    ORDER_SUCCEEDED,
)
from tests.helpers import Caller, MockAPI

SRC = Path(__file__).resolve().parent.parent / "src" / "rayacash"
ITEM = {"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}
# Un Checkout pagado (el CHECKOUT_SUCCEEDED de los tests de la 1.1.0), guardado con pickle
# (protocolo 4) por la 1.1.0 publicada: el código de `git archive v1.1.0`, con Python 3.9.
PICKLE_1_1_0 = Path(__file__).resolve().parent / "data" / "checkout-1.1.0.pickle"

# Cada alias y su nombre nuevo, como los nombra el aviso.
CHECKOUT = ("rayacash.Checkout", "rayacash.ConnectOrder")
CHECKOUT_STATUS = ("rayacash.CheckoutStatus", "rayacash.ConnectOrderStatus")
CLIENT_CHECKOUT = ("client.checkout", "client.connect")
CHECKOUT_ID = ("checkout_id", "order_id")

# El __all__ que se publicó con la 1.1.0: nada de esto puede faltar en una 1.x.
ALL_1_1_0 = [
    "DEFAULT_API_BASE",
    "VERSION",
    "APIConnectionError",
    "APIError",
    "Amount",
    "AnyIterator",
    "AppInfo",
    "AuthenticationError",
    "Balance",
    "Checkout",
    "CheckoutStatus",
    "ConflictError",
    "Event",
    "EventType",
    "IdempotencyError",
    "InvalidRequestError",
    "ListObject",
    "NotFoundError",
    "OAuth",
    "OAuthToken",
    "Payment",
    "PaymentStatus",
    "PermissionDeniedError",
    "RateLimitError",
    "RayaClient",
    "RayaError",
    "RayaObject",
    "RayaResponse",
    "RequestOptions",
    "SignatureVerificationError",
    "Transfer",
    "TransferDirection",
    "TransferStatus",
    "UnprocessableEntityError",
    "User",
    "UserType",
    "Webhook",
    "WebhookSignature",
    "__version__",
    "api_base",
    "api_key",
    "app_info",
    "async_http_client",
    "http_client",
    "log",
    "max_network_retries",
    "set_app_info",
    "timeout",
]


@contextlib.contextmanager
def warns(*aliases: tuple[str, str], at: str | None = __file__) -> Iterator[None]:
    """Exactamente los avisos de esos alias, apuntando al archivo ``at``: el de quien usó el alias.

    ``at=None`` no lo chequea: un ``asyncio.run(corrutina)`` apunta a asyncio, que la arranca.
    """
    messages = {deprecation_message(*alias) for alias in aliases}
    with pytest.warns(DeprecationWarning, match="|".join(map(re.escape, messages))) as record:
        yield
    assert {str(w.message) for w in record} == messages
    if at is not None:
        assert {w.filename for w in record} == {at}


def caller_file(call: Caller) -> str | None:
    """Con el fixture ``call``, quien llama al método es ``Caller`` (en tests/helpers.py)."""
    return helpers.__file__ if call.mode == "sync" else None


@pytest.fixture
def global_api(api: MockAPI) -> MockAPI:
    """El estilo global con el access_token de la cuenta conectada."""
    rayacash.api_key = ACCESS_TOKEN
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    return api


# --- rayacash.Checkout y rayacash.CheckoutStatus --------------------------------------------


def test_checkout_is_connect_order() -> None:
    with warns(CHECKOUT):
        checkout = rayacash.Checkout
    assert checkout is rayacash.ConnectOrder
    assert checkout.Item is rayacash.ConnectOrder.Item
    assert checkout.BankTransfer is rayacash.ConnectOrder.BankTransfer
    assert checkout.Payer is rayacash.ConnectOrder.Payer
    assert checkout.BackUrls is rayacash.ConnectOrder.BackUrls
    # La misma clase, así que también su OBJECT_NAME: en la 1.1.0 era "checkout" (el CHANGELOG
    # lo avisa).
    assert checkout.OBJECT_NAME == "connect.order"
    with warns(CHECKOUT_STATUS):
        status = rayacash.CheckoutStatus
    assert status is rayacash.ConnectOrderStatus
    assert get_args(status) == ("pending", "succeeded", "failed", "expired", "refunded")


def test_from_rayacash_import_checkout() -> None:
    with warns(CHECKOUT, CHECKOUT_STATUS):
        from rayacash import Checkout, CheckoutStatus
    assert Checkout is rayacash.ConnectOrder
    assert CheckoutStatus is rayacash.ConnectOrderStatus


def test_every_1_1_0_name_is_still_exported() -> None:
    assert set(ALL_1_1_0) <= set(rayacash.__all__)
    with warns(CHECKOUT, CHECKOUT_STATUS):
        for name in ALL_1_1_0:
            getattr(rayacash, name)
    namespace: dict[str, Any] = {}
    with warns(CHECKOUT, CHECKOUT_STATUS, at="<string>"):  # el código del exec
        exec("from rayacash import *", namespace)
    assert namespace["Checkout"] is rayacash.ConnectOrder
    assert set(ALL_1_1_0) <= set(namespace)


def test_unknown_names_are_still_attribute_errors() -> None:
    # Sin aviso: filterwarnings = error haría fallar el test.
    with pytest.raises(AttributeError, match=r"^module 'rayacash' has no attribute 'Chekout'$"):
        rayacash.Chekout  # type: ignore[attr-defined]
    assert not hasattr(rayacash, "CheckoutService")


def test_checkout_is_the_same_class_both_ways() -> None:
    with warns(CHECKOUT):
        checkout = rayacash.Checkout
    order = convert_to_raya_object(ORDER_SUCCEEDED)
    assert isinstance(order, checkout)
    assert isinstance(checkout.construct_from(ORDER_SUCCEEDED), rayacash.ConnectOrder)
    assert type(order.payer) is checkout.Payer
    assert type(order.bank_transfer) is checkout.BankTransfer
    assert type(order.back_urls) is checkout.BackUrls
    assert [type(item) for item in order["items"]] == [checkout.Item]


def test_checkout_global_style_calls_the_connect_routes(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    with warns(CHECKOUT):
        checkout = rayacash.Checkout
    api.add(201, ORDER_PENDING)
    created = call(checkout, "create", items=[ITEM], fee=500)
    assert type(created) is rayacash.ConnectOrder
    assert (api.last.method, api.last.url.path) == ("POST", "/v1/connect/orders")
    assert json.loads(api.last.content) == {"items": [ITEM], "fee": 500}

    api.add(200, ORDER_SUCCEEDED)
    succeeded = call(checkout, "retrieve", ORDER_ID)
    assert (api.last.method, api.last.url.path) == ("GET", f"/v1/connect/orders/{ORDER_ID}")

    api.add(200, ORDER_REFUNDED)
    assert call(checkout, "refund", ORDER_ID, idempotency_key="r-1").status == "refunded"
    assert api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"
    assert api.last.headers["idempotency-key"] == "r-1"

    # checkout.refund() desde el objeto, como en la 1.1.0.
    api.add(200, ORDER_REFUNDED)
    assert call(succeeded, "refund", idempotency_key="r-2").status == "refunded"
    assert api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"
    assert api.last.headers["idempotency-key"] == "r-2"
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


# --- Los pickles de la 1.1.0 -----------------------------------------------------------------


def test_a_1_1_0_pickle_loads_as_a_connect_order(global_api: MockAPI) -> None:
    # Un Checkout que la 1.1.0 guardó con pickle (en un caché, una cola…) nombra su clase como
    # rayacash._checkout.Checkout y sus ítems como rayacash._checkout.Checkout.Item.
    data = PICKLE_1_1_0.read_bytes()
    assert b"rayacash._checkout" in data
    assert b"Checkout.Item" in data
    order = pickle.loads(data)  # sin aviso (filterwarnings = error): es un dato, no tu código
    assert type(order) is rayacash.ConnectOrder
    assert order.to_dict() == {**ORDER_SUCCEEDED, "object": "checkout"}  # tal como se guardó
    assert [type(item) for item in order["items"]] == [rayacash.ConnectOrder.Item]
    assert type(order.bank_transfer) is rayacash.ConnectOrder.BankTransfer
    assert type(order.payer) is rayacash.ConnectOrder.Payer
    assert type(order.back_urls) is rayacash.ConnectOrder.BackUrls

    # Es un ConnectOrder como cualquier otro: el reembolso va a la ruta nueva.
    global_api.add(200, ORDER_REFUNDED)
    assert order.refund(idempotency_key="r-1").status == "refunded"
    assert global_api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"

    # Y un pickle nuevo ya no nombra el módulo de la 1.1.0, que se va en la 2.0.0.
    again = pickle.dumps(order)
    assert b"rayacash._connect_order" in again
    assert b"rayacash._checkout" not in again
    assert type(pickle.loads(again)) is rayacash.ConnectOrder


def test_the_1_1_0_module_is_only_kept_for_its_pickles() -> None:
    from rayacash import _checkout

    assert _checkout.__all__ == ["Checkout", "CheckoutStatus"]
    assert _checkout.Checkout is rayacash.ConnectOrder
    assert _checkout.CheckoutStatus is rayacash.ConnectOrderStatus


# --- client.checkout ---------------------------------------------------------------------------


def test_client_checkout_is_client_connect(connected: rayacash.RayaClient) -> None:
    with warns(CLIENT_CHECKOUT):
        service = connected.checkout
    assert service is connected.connect
    with warns(CLIENT_CHECKOUT):
        orders = connected.checkout.orders
    assert orders is connected.connect.orders


def test_client_checkout_orders_call_the_connect_routes(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    with warns(CLIENT_CHECKOUT):
        orders = connected.checkout.orders
    api.add(201, ORDER_PENDING)
    order = call(orders, "create", items=[ITEM], fee=500, idempotency_key="pedido-1042")
    assert type(order) is rayacash.ConnectOrder
    assert (api.last.method, api.last.url.path) == ("POST", "/v1/connect/orders")
    assert json.loads(api.last.content) == {"items": [ITEM], "fee": 500}
    assert api.last.headers["idempotency-key"] == "pedido-1042"

    api.add(200, ORDER_SUCCEEDED)
    assert call(orders, "retrieve", ORDER_ID).status == "succeeded"
    assert (api.last.method, api.last.url.path) == ("GET", f"/v1/connect/orders/{ORDER_ID}")

    api.add(200, ORDER_REFUNDED)
    assert call(orders, "refund", ORDER_ID, idempotency_key="r-1").status == "refunded"
    assert (api.last.method, api.last.url.path) == (
        "POST",
        f"/v1/connect/orders/{ORDER_ID}/refund",
    )
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_the_1_1_0_readme_example_runs_unchanged(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    # El paso 4 del README de la 1.1.0, con los nombres de entonces.
    api.add(201, ORDER_PENDING)
    api.add(200, ORDER_SUCCEEDED)
    api.add(200, ORDER_REFUNDED)
    with warns(CLIENT_CHECKOUT):
        checkout = connected.checkout.orders.create(items=[ITEM], fee=500)
        checkout = connected.checkout.orders.retrieve(checkout.id)
        if checkout.status == "succeeded":
            checkout = connected.checkout.orders.refund(checkout.id, idempotency_key="r-1")
    assert checkout.status == "refunded"
    assert [(r.method, r.url.path) for r in api.requests] == [
        ("POST", "/v1/connect/orders"),
        ("GET", f"/v1/connect/orders/{ORDER_ID}"),
        ("POST", f"/v1/connect/orders/{ORDER_ID}/refund"),
    ]


# En la 1.1.0, client.checkout era un atributo común: los tests de tus usuarios lo reemplazan.


def test_client_checkout_can_be_assigned_and_deleted(connected: rayacash.RayaClient) -> None:
    fake = mock.MagicMock()
    with warns(CLIENT_CHECKOUT):
        connected.checkout = fake
    with warns(CLIENT_CHECKOUT):
        assert connected.checkout is fake
    assert connected.connect is not fake  # el reemplazo es solo de client.checkout
    with warns(CLIENT_CHECKOUT):
        del connected.checkout
    with warns(CLIENT_CHECKOUT):
        assert connected.checkout is connected.connect
    with warns(CLIENT_CHECKOUT):
        del connected.checkout  # sin reemplazo no hay nada que sacar: no falla
    # Asignarle client.connect también saca el reemplazo: vuelve a seguir a client.connect.
    with warns(CLIENT_CHECKOUT):
        connected.checkout = fake
        connected.checkout = connected.connect
    assert "checkout" not in vars(connected)


def test_mock_patch_object_replaces_and_restores_client_checkout(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    # mock lee, asigna y borra client.checkout desde unittest/mock.py: esos avisos apuntan ahí.
    created = rayacash.ConnectOrder.construct_from(ORDER_PENDING)
    with warns(CLIENT_CHECKOUT, at=None), mock.patch.object(connected, "checkout") as fake:
        fake.orders.create.return_value = created
        assert connected.checkout.orders.create(items=[ITEM]) is created
        assert connected.connect is not fake
    with warns(CLIENT_CHECKOUT):
        assert connected.checkout is connected.connect
    assert "checkout" not in vars(connected)
    assert api.requests == []

    # Si ya lo habías reemplazado, mock restaura ese reemplazo (y anidado, el de afuera).
    first = mock.MagicMock()
    with warns(CLIENT_CHECKOUT, at=None):
        connected.checkout = first
        with mock.patch.object(connected, "checkout") as outer:
            with mock.patch.object(connected, "checkout") as inner:
                assert connected.checkout is inner
            assert connected.checkout is outer
        assert connected.checkout is first


def test_monkeypatch_setattr_replaces_and_restores_client_checkout(
    connected: rayacash.RayaClient,
) -> None:
    # MonkeyPatch.context() es el monkeypatch de pytest con undo() al salir, que acá cae dentro
    # de warns (el fixture lo deshace después del test, cuando un aviso ya es un error).
    fake = mock.MagicMock()
    with warns(CLIENT_CHECKOUT, at=None), pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(connected, "checkout", fake)
        assert connected.checkout is fake
    with warns(CLIENT_CHECKOUT):
        assert connected.checkout is connected.connect
    # undo() le volvió a asignar client.connect, así que sigue a client.connect si cambia.
    assert "checkout" not in vars(connected)
    other = mock.MagicMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(connected, "connect", other)
        with warns(CLIENT_CHECKOUT):
            assert connected.checkout is other


# --- checkout_id= ------------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), [("retrieve", ""), ("refund", "/refund")])
def test_checkout_id_still_works_on_connect_orders(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller, method: str, path: str
) -> None:
    api.add(200, ORDER_REFUNDED)
    with warns(CHECKOUT_ID, at=caller_file(call)):
        order = call(connected.connect.orders, method, checkout_id=ORDER_ID)
    assert order.id == ORDER_ID
    assert api.last.url.path == f"/v1/connect/orders/{ORDER_ID}{path}"


@pytest.mark.parametrize(("method", "path"), [("retrieve", ""), ("refund", "/refund")])
def test_checkout_id_still_works_in_the_global_style(
    global_api: MockAPI, call: Caller, method: str, path: str
) -> None:
    global_api.add(200, ORDER_REFUNDED)
    with warns(CHECKOUT_ID, at=caller_file(call)):
        order = call(rayacash.ConnectOrder, method, checkout_id=ORDER_ID)
    assert type(order) is rayacash.ConnectOrder
    assert global_api.last.url.path == f"/v1/connect/orders/{ORDER_ID}{path}"


def test_checkout_id_keeps_the_other_arguments(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, ORDER_REFUNDED)
    with warns(CHECKOUT_ID):
        connected.connect.orders.refund(checkout_id=ORDER_ID, idempotency_key="reembolso-1")
    assert api.last.headers["idempotency-key"] == "reembolso-1"
    other_token = "raya_at_live_" + "z" * 48
    api.add(200, ORDER_SUCCEEDED)
    with warns(CHECKOUT_ID):
        connected.connect.orders.retrieve(checkout_id=ORDER_ID, options={"api_key": other_token})
    assert api.last.headers["authorization"] == f"Bearer {other_token}"


def test_a_1_1_0_global_snippet_runs_unchanged(global_api: MockAPI) -> None:
    global_api.add(200, ORDER_SUCCEEDED)
    global_api.add(200, ORDER_REFUNDED)
    with warns(CHECKOUT, CHECKOUT_ID):
        checkout = rayacash.Checkout.retrieve(checkout_id=ORDER_ID)
        refunded = rayacash.Checkout.refund(checkout_id=checkout.id, idempotency_key="r-1")
    assert refunded.status == "refunded"
    assert [r.url.path for r in global_api.requests] == [
        f"/v1/connect/orders/{ORDER_ID}",
        f"/v1/connect/orders/{ORDER_ID}/refund",
    ]


def test_checkout_id_is_validated_like_order_id(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    with pytest.raises(ValueError, match=r"^order_id no puede estar vacío"), warns(CHECKOUT_ID):
        connected.connect.orders.refund(checkout_id=" ")
    assert api.requests == []


def test_checkout_id_and_order_id_together_are_a_type_error(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    orders: Any = connected.connect.orders  # llamadas que el type checker ya rechaza
    with pytest.raises(TypeError, match=r"^Pasá order_id o checkout_id \(deprecado\), no los dos"):
        orders.retrieve(order_id=ORDER_ID, checkout_id=ORDER_ID)
    duplicated = "multiple values for argument 'order_id'"
    with pytest.raises(TypeError, match=duplicated), warns(CHECKOUT_ID):
        orders.retrieve(ORDER_ID, checkout_id=ORDER_ID)
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'order_id'"):
        orders.retrieve()
    assert api.requests == []


# --- Lo que renombró la API --------------------------------------------------------------------


def test_the_registry_maps_the_1_1_0_object_name() -> None:
    assert OBJECT_CLASSES["checkout"] is rayacash.ConnectOrder
    assert OBJECT_CLASSES["connect.order"] is rayacash.ConnectOrder
    legacy = {**ORDER_SUCCEEDED, "object": "checkout"}
    order = convert_to_raya_object(legacy)
    assert type(order) is rayacash.ConnectOrder
    assert order.object == "checkout"  # tal como vino
    assert order.to_dict() == legacy


def test_a_resent_1_1_0_event_still_builds_a_connect_order(global_api: MockAPI) -> None:
    # Un evento de antes del cambio, reenviado desde el dashboard: type y object con los nombres
    # de la 1.1.0.
    legacy = {
        **EVENT_ORDER_SUCCEEDED,
        "type": "checkout.succeeded",
        "data": {"object": {**ORDER_SUCCEEDED, "object": "checkout"}},
    }
    body = json.dumps(legacy)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert event.type == "checkout.succeeded"
    order = event.data.object
    assert isinstance(order, rayacash.ConnectOrder)
    assert type(order) is rayacash.ConnectOrder
    global_api.add(200, ORDER_REFUNDED)
    order.refund(idempotency_key="r-1")
    assert global_api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"


def test_event_type_keeps_the_1_1_0_names_as_legacy() -> None:
    names = get_args(rayacash.EventType)
    assert len(names) == len(set(names))
    assert {
        "connect.order.created",
        "connect.order.succeeded",
        "connect.order.failed",
        "connect.order.refunded",
    } <= set(names)
    # Al final, como legacy: la API ya no los emite.
    assert names[-4:] == (
        "checkout.created",
        "checkout.succeeded",
        "checkout.failed",
        "checkout.refunded",
    )


# --- Los avisos ----------------------------------------------------------------------------------


def test_the_deprecated_markers_say_what_the_warnings_say() -> None:
    # Los type checkers solo leen un @deprecated("…") literal: que diga lo mismo que el aviso.
    markers: list[str] = []
    for path in sorted(SRC.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "deprecated"
            ):
                (message,) = node.args
                assert isinstance(message, ast.Constant), path.name
                assert isinstance(message.value, str), path.name
                markers.append(message.value)
    assert sorted(set(markers)) == sorted(
        {deprecation_message(*CLIENT_CHECKOUT), deprecation_message(*CHECKOUT_ID)}
    )
    # checkout_id=: retrieve y refund, con sus *_async, en client.connect.orders (4) y en
    # rayacash.ConnectOrder (4: retrieve es un classmethod; refund, el descriptor de la clase).
    assert markers.count(deprecation_message(*CHECKOUT_ID)) == 8
    # client.checkout: el getter, el setter y el deleter de la property.
    assert markers.count(deprecation_message(*CLIENT_CHECKOUT)) == 3
    checkout = vars(rayacash.RayaClient)["checkout"]
    for accessor in (checkout.fget, checkout.fset, checkout.fdel):
        assert accessor.__deprecated__ == deprecation_message(*CLIENT_CHECKOUT)


def test_the_new_names_never_warn(connected: rayacash.RayaClient, api: MockAPI) -> None:
    # filterwarnings = error: cualquier aviso haría fallar el test.
    api.add(200, ORDER_SUCCEEDED)
    api.add(200, ORDER_REFUNDED)
    order = connected.connect.orders.retrieve(order_id=ORDER_ID)
    connected.connect.orders.refund(order.id, idempotency_key="r-1")
    assert rayacash.ConnectOrder.Item is not None
    assert rayacash.ConnectOrderStatus is not None
