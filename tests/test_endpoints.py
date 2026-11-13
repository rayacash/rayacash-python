"""Los 21 endpoints, en sync y en async: método, ruta, query, body y headers exactos."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest

import rayacash
from tests.fixtures import (
    BALANCE,
    PAYMENT_ID,
    PAYMENT_PENDING,
    PAYMENT_REFUNDED,
    PAYMENT_SUCCEEDED,
    TRANSFER_INBOUND,
    TRANSFER_LIST,
    TRANSFER_OUTBOUND_PENDING,
)
from tests.fixtures_apps import (
    ACCESS_TOKEN,
    APP_CLIENT_ID,
    APP_CLIENT_SECRET,
    AUTH_CODE,
    NOTIFICATION_URL,
    OAUTH_TOKEN,
    ORDER_ID,
    ORDER_PENDING,
    ORDER_REFUNDED,
    ORDER_SUCCEEDED,
    PAYOUT_COMPLETED,
    PAYOUT_DESTINATION,
    PAYOUT_ID,
    PAYOUT_LIST,
    PAYOUT_ORIGIN_ACCOUNT,
    PAYOUT_PENDING,
    REDIRECT_URI,
    USER,
    USER_ID,
)
from tests.fixtures_identity import (
    BIOMETRIC_ID,
    NEXT_CURSOR,
    VERIFICATION_BIOMETRIC_VERIFIED,
    VERIFICATION_CANCELED,
    VERIFICATION_DECLINED,
    VERIFICATION_FILES,
    VERIFICATION_ID,
    VERIFICATION_LIST,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
)
from tests.fixtures_sandbox import (
    SANDBOX_KEY,
    SANDBOX_ORDER_ID,
    SANDBOX_ORDER_SUCCEEDED,
    SANDBOX_PAYMENT_FAILED,
    SANDBOX_PAYMENT_ID,
    SANDBOX_PAYMENT_OVERPAID,
    SANDBOX_PAYMENT_SUCCEEDED,
)
from tests.helpers import OTHER_KEY, TEST_KEY, Caller, MockAPI

IDEMPOTENCY_KEY = "9b2f6c4e-1d3a-4e8b-a5c7-0f9e8d7c6b5a"


def test_balance_retrieve(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, BALANCE)
    balance = call(client.balance, "retrieve")
    assert type(balance) is rayacash.Balance
    assert balance.available == 152340.5
    assert balance.currency == "ARS"
    request = api.last
    assert (request.method, str(request.url)) == ("GET", "https://api.raya.cash/v1/balance")
    assert request.content == b""
    assert "idempotency-key" not in request.headers
    assert balance.last_response is not None
    assert balance.last_response.request_id == "req_test00000000000000000001"
    assert balance.last_response.http_status == 200
    assert balance.last_response.idempotency_key is None


def test_transfer_create(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(201, TRANSFER_OUTBOUND_PENDING)
    transfer = call(
        client.transfers,
        "create",
        amount=Decimal("25000.00"),
        destination="0000123380736153041182",
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert type(transfer) is rayacash.Transfer
    assert transfer.status == "pending"
    assert transfer.counterparty.name == "Proveedora Ejemplo S. A."
    request = api.last
    assert (request.method, str(request.url)) == ("POST", "https://api.raya.cash/v1/transfers")
    assert request.content == b'{"amount":25000,"destination":"0000123380736153041182"}'
    assert request.headers["content-type"] == "application/json"
    assert request.headers["idempotency-key"] == IDEMPOTENCY_KEY
    assert transfer.last_response is not None
    assert transfer.last_response.idempotency_key == IDEMPOTENCY_KEY


@pytest.mark.parametrize(
    ("amount", "expected"), [(25000.5, b"25000.5"), ("25000.50", b"25000.5"), (1, b"1")]
)
def test_transfer_amount_forms(
    client: rayacash.RayaClient, api: MockAPI, amount: object, expected: bytes
) -> None:
    api.add(201, TRANSFER_OUTBOUND_PENDING)
    client.transfers.create(amount=amount, destination="proveedor.ejemplo", idempotency_key="k")  # type: ignore[arg-type]
    assert api.last.content == b'{"amount":' + expected + b',"destination":"proveedor.ejemplo"}'


def test_transfer_create_requires_an_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    with pytest.raises(TypeError):
        client.transfers.create(amount=1, destination="x")  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="idempotency_key"):
        client.transfers.create(amount=1, destination="x", idempotency_key=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="idempotency_key"):
        client.transfers.create(amount=1, destination="x", idempotency_key="con espacios")
    with pytest.raises(TypeError, match="destination"):
        client.transfers.create(amount=1, destination=123, idempotency_key="k")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="amount"):
        client.transfers.create(amount=True, destination="x", idempotency_key="k")
    assert api.requests == []


def test_transfer_retrieve(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, TRANSFER_INBOUND)
    transfer = call(client.transfers, "retrieve", TRANSFER_INBOUND["id"])
    assert type(transfer) is rayacash.Transfer
    assert transfer.direction == "inbound"
    assert transfer.net_amount == 48169.59
    assert (api.last.method, api.last.url.path) == (
        "GET",
        f"/v1/transfers/{TRANSFER_INBOUND['id']}",
    )


def test_ids_are_encoded_and_never_empty(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(404, {"error": {"code": "TRANSFER_NOT_FOUND", "message": "x", "data": None}})
    with pytest.raises(rayacash.NotFoundError):
        client.transfers.retrieve("../balance")
    assert api.last.url.raw_path == b"/v1/transfers/..%2Fbalance"
    with pytest.raises(ValueError, match="transfer_id"):
        client.transfers.retrieve("")
    with pytest.raises(ValueError, match="payment_id"):
        client.payments.refund(" ")
    with pytest.raises(ValueError, match="user_id"):
        client.users.retrieve("")
    with pytest.raises(ValueError, match="order_id"):
        client.connect.orders.refund(" ")
    with pytest.raises(TypeError, match="order_id"):
        client.connect.orders.retrieve(None)  # type: ignore[call-overload]
    with pytest.raises(ValueError, match="payout_id"):
        client.connect.payouts.retrieve(" ")
    with pytest.raises(TypeError, match="payout_id"):
        client.connect.payouts.retrieve(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [".", ".."])
def test_dot_segment_ids_fail_before_sending(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, value: str
) -> None:
    # httpx resolvía los segmentos: transfers.retrieve(".") pedía la lista y refund(".."),
    # /v1/refund.
    with pytest.raises(ValueError, match=r'^transfer_id no puede ser "\." ni "\.\."\.$'):
        call(client.transfers, "retrieve", value)
    with pytest.raises(ValueError, match=r'^payment_id no puede ser "\." ni "\.\."\.$'):
        call(client.payments, "retrieve", value)
    with pytest.raises(ValueError, match=r'^payment_id no puede ser "\." ni "\.\."\.$'):
        call(client.payments, "refund", value)
    with pytest.raises(ValueError, match=r'^user_id no puede ser "\." ni "\.\."\.$'):
        call(client.users, "retrieve", value)
    with pytest.raises(ValueError, match=r'^order_id no puede ser "\." ni "\.\."\.$'):
        call(client.connect.orders, "retrieve", value)
    with pytest.raises(ValueError, match=r'^order_id no puede ser "\." ni "\.\."\.$'):
        call(client.connect.orders, "refund", value)
    with pytest.raises(ValueError, match=r'^payout_id no puede ser "\." ni "\.\."\.$'):
        call(client.connect.payouts, "retrieve", value)
    assert api.requests == []


def test_transfer_list(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, TRANSFER_LIST)
    page = call(
        client.transfers,
        "list",
        direction="inbound",
        created_gte=datetime(2026, 10, 23, 3, tzinfo=timezone.utc),
        created_lt="2026-10-24T00:00:00-03:00",
        limit=2,
    )
    assert type(page) is rayacash.ListObject
    assert [type(t) for t in page] == [rayacash.Transfer, rayacash.Transfer]
    assert page.has_more is True
    request = api.last
    assert (request.method, request.url.path) == ("GET", "/v1/transfers")
    assert dict(request.url.params) == {
        "direction": "inbound",
        "created_gte": "2026-10-23T03:00:00+00:00",
        "created_lt": "2026-10-24T00:00:00-03:00",
        "limit": "2",
    }


def test_transfer_list_without_filters(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, {**TRANSFER_LIST, "has_more": False, "next_cursor": None})
    client.transfers.list()
    assert str(api.last.url) == "https://api.raya.cash/v1/transfers"


def test_payment_create(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(201, PAYMENT_PENDING)
    payment = call(
        client.payments,
        "create",
        amount=15000,
        description="Pedido #1042",
        external_reference="pedido-1042",
        return_url="https://tienda.example.com/pedidos/1042",
        metadata={"cliente_id": "8812"},
    )
    assert type(payment) is rayacash.Payment
    assert payment.bank_transfer.cvu == "0000123322813466534007"
    assert payment.checkout_url.endswith(PAYMENT_ID)
    request = api.last
    assert (request.method, request.url.path) == ("POST", "/v1/payments")
    assert api.last_json() == {
        "amount": 15000,
        "description": "Pedido #1042",
        "external_reference": "pedido-1042",
        "return_url": "https://tienda.example.com/pedidos/1042",
        "metadata": {"cliente_id": "8812"},
    }
    # Sin clave propia, generamos un UUID v4 para esta llamada.
    assert uuid.UUID(request.headers["idempotency-key"]).version == 4


def test_each_call_without_a_key_gets_its_own(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    # Una clave por llamada (no por cliente ni por proceso): dos pagos iguales son dos pagos.
    for _ in range(2):
        api.add(201, PAYMENT_PENDING)
        call(client.payments, "create", amount=15000)
    for _ in range(2):
        api.add(200, PAYMENT_REFUNDED)
        call(client.payments, "refund", PAYMENT_ID)
    keys = [request.headers["idempotency-key"] for request in api.requests]
    assert len(set(keys)) == 4
    assert all(uuid.UUID(key).version == 4 for key in keys)


def test_payment_create_sends_only_what_you_pass(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(201, PAYMENT_PENDING)
    client.payments.create(amount=Decimal("15000.50"), idempotency_key="pedido-1042-pago")
    assert api.last.content == b'{"amount":15000.5}'
    assert api.last.headers["idempotency-key"] == "pedido-1042-pago"
    with pytest.raises(TypeError, match="metadata"):
        client.payments.create(amount=1, metadata=[("a", "b")])  # type: ignore[arg-type]


def test_payment_retrieve(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, PAYMENT_SUCCEEDED)
    payment = call(client.payments, "retrieve", PAYMENT_ID)
    assert payment.status == "succeeded"
    assert payment.payer.account == "0000123300602983525937"
    assert (api.last.method, api.last.url.path) == ("GET", f"/v1/payments/{PAYMENT_ID}")


def test_payment_refund(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, PAYMENT_REFUNDED)
    payment = call(client.payments, "refund", PAYMENT_ID, idempotency_key="reembolso-1")
    assert payment.status == "refunded"
    request = api.last
    assert (request.method, request.url.path) == ("POST", f"/v1/payments/{PAYMENT_ID}/refund")
    assert request.content == b""  # el reembolso va sin body
    assert "content-type" not in request.headers
    assert request.headers["content-length"] == "0"
    assert request.headers["idempotency-key"] == "reembolso-1"


def test_errors_come_with_the_request_id(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(422, "INSUFFICIENT_BALANCE", "El monto supera tu saldo disponible.")
    with pytest.raises(rayacash.UnprocessableEntityError) as info:
        call(
            client.transfers,
            "create",
            amount=10**9,
            destination="alias.prueba",
            idempotency_key="k",
        )
    error = info.value
    assert error.code == "INSUFFICIENT_BALANCE"
    assert error.request_id == "req_test00000000000000000001"
    assert error.idempotency_key == "k"
    assert len(api.requests) == 1  # los 4xx no se reintentan


# --- Raya Connect: oauth.token, users.retrieve y connect.orders.* -------------------------------

ITEM = {"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}


def test_oauth_token(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, OAUTH_TOKEN)
    token = call(client.oauth, "token", APP_CLIENT_ID, APP_CLIENT_SECRET, AUTH_CODE, REDIRECT_URI)
    assert type(token) is rayacash.OAuthToken
    assert token.access_token == ACCESS_TOKEN
    assert token.user_id == USER_ID
    assert token.token_type == "Bearer"
    assert token.scope == "orders profile"
    assert token.expires_in is None
    assert token.refresh_token is None
    request = api.last
    assert (request.method, str(request.url)) == ("POST", "https://api.raya.cash/v1/oauth/token")
    # La única request sin Authorization: la app se identifica en el body. Y sin Idempotency-Key:
    # el code se canjea una sola vez.
    assert "authorization" not in request.headers
    assert "idempotency-key" not in request.headers
    assert request.headers["content-type"] == "application/json"
    assert api.last_json() == {
        "client_id": APP_CLIENT_ID,
        "client_secret": APP_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": AUTH_CODE,
        "redirect_uri": REDIRECT_URI,
    }
    assert token.last_response is not None
    assert token.last_response.idempotency_key is None
    assert token.last_response.request_id == "req_test00000000000000000001"


def test_oauth_token_needs_no_key_and_the_token_works_as_one(api: MockAPI, call: Caller) -> None:
    client = api.client(None)  # sin api_key ni RAYA_SECRET_KEY (conftest la borra)
    api.add(200, OAUTH_TOKEN)
    token = call(
        client.oauth,
        "token",
        client_id=APP_CLIENT_ID,
        client_secret=APP_CLIENT_SECRET,
        code=AUTH_CODE,
        redirect_uri=REDIRECT_URI,
    )
    assert "authorization" not in api.last.headers
    assert api.last_json()["grant_type"] == "authorization_code"
    # Con lo que vino, un cliente que opera por esa cuenta.
    connected = api.client(token.access_token)
    api.add(200, USER)
    user = call(connected.users, "retrieve", token.user_id)
    assert type(user) is rayacash.User
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
    # Y el mismo cliente sin clave sigue sin poder hacer las demás requests.
    with pytest.raises(rayacash.AuthenticationError) as info:
        client.users.retrieve("me")
    assert info.value.code == "API_KEY_MISSING"
    assert len(api.requests) == 2


def test_oauth_token_errors_come_without_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(400, "OAUTH_GRANT_INVALID", "El code no es válido.")
    with pytest.raises(rayacash.InvalidRequestError) as info:
        call(client.oauth, "token", APP_CLIENT_ID, APP_CLIENT_SECRET, "usado", REDIRECT_URI)
    assert info.value.code == "OAUTH_GRANT_INVALID"
    assert info.value.idempotency_key is None
    api.add_error(401, "OAUTH_CLIENT_INVALID", "El client_id o el client_secret no son válidos.")
    with pytest.raises(rayacash.AuthenticationError) as denied:
        call(client.oauth, "token", APP_CLIENT_ID, "raya_cs_live_otra", AUTH_CODE, REDIRECT_URI)
    assert denied.value.code == "OAUTH_CLIENT_INVALID"
    assert denied.value.http_status == 401
    assert denied.value.idempotency_key is None


@pytest.mark.parametrize(
    ("kwargs", "name"),
    [
        ({"client_id": 7650337728110670}, "client_id"),
        ({"client_secret": None}, "client_secret"),
        ({"code": b"c0d3"}, "code"),
        ({"redirect_uri": ["https://tienda.example.com/raya/callback"]}, "redirect_uri"),
    ],
)
def test_oauth_token_rejects_non_strings(
    client: rayacash.RayaClient, api: MockAPI, kwargs: dict[str, object], name: str
) -> None:
    params: dict[str, object] = {
        "client_id": APP_CLIENT_ID,
        "client_secret": APP_CLIENT_SECRET,
        "code": AUTH_CODE,
        "redirect_uri": REDIRECT_URI,
        **kwargs,
    }
    with pytest.raises(TypeError, match=f"^{name} tiene que ser un str"):
        client.oauth.token(**params)  # type: ignore[arg-type]
    assert api.requests == []


def test_oauth_token_hint_names_the_client_secret_of_a_sandbox_app(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    # La pista del client_secret nombra también el de una app de un sandbox.
    with pytest.raises(TypeError) as info:
        client.oauth.token(
            client_id=APP_CLIENT_ID,
            client_secret=None,  # type: ignore[arg-type]
            code=AUTH_CODE,
            redirect_uri=REDIRECT_URI,
        )
    assert str(info.value) == (
        "client_secret tiene que ser un str (raya_cs_live_…, de Developers › Apps, o "
        "raya_cs_test_…, el de una app de un sandbox), no NoneType."
    )
    assert api.requests == []


def test_user_retrieve(connected: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, USER)
    user = call(connected.users, "retrieve", USER_ID)
    assert type(user) is rayacash.User
    assert user.type == "personal"
    assert user.identification is not None
    assert user.identification.type == "DNI"
    assert user.identification.number == "34567890"
    assert user.address is not None
    assert user.address.city == "Rosario"
    assert user.merchant is not None
    assert user.merchant.name == "Almacén Ejemplo"
    assert user.business is None
    request = api.last
    assert (request.method, request.url.path) == ("GET", f"/v1/users/{USER_ID}")
    assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert request.content == b""
    assert "idempotency-key" not in request.headers


def test_user_retrieve_me(connected: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, USER)
    assert connected.users.retrieve("me").id == USER_ID
    assert str(api.last.url) == "https://api.raya.cash/v1/users/me"


def test_user_not_found(connected: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add_error(404, "USER_NOT_FOUND", "No encontramos ese usuario.")
    with pytest.raises(rayacash.NotFoundError) as info:
        call(connected.users, "retrieve", "5b1e7c3a-9d2f-4e6b-8a0c-7f3d1b9e2c54")
    assert info.value.code == "USER_NOT_FOUND"


def test_connect_order_create(connected: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(201, ORDER_PENDING)
    order = call(
        connected.connect.orders,
        "create",
        items=[ITEM],
        fee=500,
        external_reference="pedido-1042",
        back_urls={
            "success": "https://tienda.example.com/pedidos/1042",
            "failure": "https://tienda.example.com/pedidos/1042/error",
        },
        auto_return="approved",
        notification_url=NOTIFICATION_URL,
        metadata={"pedido_id": "1042"},
    )
    assert type(order) is rayacash.ConnectOrder
    assert order.object == "connect.order"
    assert order.status == "pending"
    assert order.fee == 500
    assert order.net_amount == 44500
    assert order.account == USER_ID
    assert order["items"][0].unit_price == 45000
    assert order.bank_transfer.cvu == "0000123390456538582824"
    assert order.checkout_url == f"https://raya.cash/checkout/{ORDER_ID}"  # la página no cambia
    request = api.last
    assert (request.method, request.url.path) == ("POST", "/v1/connect/orders")
    assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert api.last_json() == {
        "items": [ITEM],
        "fee": 500,
        "external_reference": "pedido-1042",
        "metadata": {"pedido_id": "1042"},
        "back_urls": {
            "success": "https://tienda.example.com/pedidos/1042",
            "failure": "https://tienda.example.com/pedidos/1042/error",
        },
        "auto_return": "approved",
        "notification_url": NOTIFICATION_URL,
    }
    # Sin clave propia, generamos un UUID v4 para esta llamada, como en payments.create.
    assert uuid.UUID(request.headers["idempotency-key"]).version == 4
    assert order.last_response is not None
    assert order.last_response.idempotency_key == request.headers["idempotency-key"]


def test_connect_order_create_sends_only_what_you_pass_and_exact_amounts(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(201, ORDER_PENDING)
    connected.connect.orders.create(items=[ITEM], idempotency_key="pedido-1042-connect")
    assert (
        api.last.content == b'{"items":[{"title":"Pedido 1042","quantity":1,"unit_price":45000}]}'
    )
    assert api.last.headers["idempotency-key"] == "pedido-1042-connect"

    api.add(201, ORDER_PENDING)
    connected.connect.orders.create(
        items=[
            {"title": "Café", "quantity": 2, "unit_price": Decimal("1500.50")},
            {"title": "Medialunas", "quantity": 6, "unit_price": "350.00"},
        ],
        fee=Decimal("100.00"),
        description="Desayuno",
        expires_in=3600,
    )
    assert api.last.content == (
        b'{"items":[{"title":"Caf\\u00e9","quantity":2,"unit_price":1500.5},'
        b'{"title":"Medialunas","quantity":6,"unit_price":350}],'
        b'"fee":100,"description":"Desayuno","expires_in":3600}'
    )


def test_connect_order_create_each_call_gets_its_own_key(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    for _ in range(2):
        api.add(201, ORDER_PENDING)
        call(connected.connect.orders, "create", items=[ITEM])
    for _ in range(2):
        api.add(200, ORDER_REFUNDED)
        call(connected.connect.orders, "refund", ORDER_ID)
    keys = [request.headers["idempotency-key"] for request in api.requests]
    assert len(set(keys)) == 4
    assert all(uuid.UUID(key).version == 4 for key in keys)


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"items": {"title": "x", "quantity": 1, "unit_price": 1}}, TypeError, "^items tiene"),
        ({"items": "Pedido 1042"}, TypeError, "^items tiene"),
        ({"items": ["Pedido 1042"]}, TypeError, r"^items\[0\] tiene"),
        ({"items": [ITEM, {**ITEM, "unit_price": True}]}, TypeError, r"^items\[1\]\.unit_price"),
        ({"items": [{**ITEM, "unit_price": float("inf")}]}, ValueError, r"^items\[0\]\.unit_price"),
        ({"items": [{**ITEM, "unit_price": "45.000,50"}]}, ValueError, r"^items\[0\]\.unit_price"),
        ({"items": [ITEM], "fee": True}, TypeError, "^fee"),
        ({"items": [ITEM], "fee": "quinientos"}, ValueError, "^fee"),
        ({"items": [ITEM], "metadata": [("a", "b")]}, TypeError, "^metadata"),
        ({"items": [ITEM], "back_urls": "https://tienda.example.com"}, TypeError, "^back_urls"),
        ({"items": [ITEM], "expires_in": 600.0}, TypeError, "^expires_in"),
        ({"items": [ITEM], "expires_in": True}, TypeError, "^expires_in"),
        ({"items": [ITEM], "idempotency_key": "con espacios"}, ValueError, "idempotency_key"),
    ],
)
def test_connect_order_create_rejects_bad_shapes_before_sending(
    connected: rayacash.RayaClient,
    api: MockAPI,
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        connected.connect.orders.create(**kwargs)  # type: ignore[arg-type]
    assert api.requests == []


def test_connect_order_items_travel_as_given_and_the_api_validates_them(
    connected: rayacash.RayaClient, api: MockAPI
) -> None:
    # Una clave de más o un unit_price que falta no se validan acá: la API responde con el campo.
    api.add_error(400, "PARAMETER_UNKNOWN", "Parámetro desconocido.", {"field": "items[0].sku"})
    with pytest.raises(rayacash.InvalidRequestError) as info:
        connected.connect.orders.create(items=[{**ITEM, "sku": "A-1"}])
    assert info.value.param == "items[0].sku"
    assert api.last_json()["items"][0]["sku"] == "A-1"
    api.add_error(400, "PARAMETER_MISSING", "Falta unit_price.", {"field": "items[0].unit_price"})
    with pytest.raises(rayacash.InvalidRequestError) as info:
        connected.connect.orders.create(items=[{"title": "Pedido 1042", "quantity": 1}])
    assert info.value.param == "items[0].unit_price"
    assert api.last_json()["items"] == [{"title": "Pedido 1042", "quantity": 1}]


def test_connect_order_create_without_merchant(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(
        403,
        "CONNECTED_ACCOUNT_NOT_CONFIGURED",
        "La cuenta conectada todavía no configuró su negocio en Raya.",
    )
    with pytest.raises(rayacash.PermissionDeniedError) as info:
        call(connected.connect.orders, "create", items=[ITEM], fee=500)
    assert info.value.code == "CONNECTED_ACCOUNT_NOT_CONFIGURED"
    assert len(api.requests) == 1  # los 4xx no se reintentan


def test_connect_order_retrieve(connected: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, ORDER_SUCCEEDED)
    order = call(connected.connect.orders, "retrieve", ORDER_ID)
    assert type(order) is rayacash.ConnectOrder
    assert order.status == "succeeded"
    assert order.amount_received == 45000
    assert order.payer is not None
    assert order.payer.account == "0000123300602983525937"
    assert order.paid_at == "2026-10-24T16:07:41Z"
    assert (api.last.method, api.last.url.path) == ("GET", f"/v1/connect/orders/{ORDER_ID}")
    assert api.last.content == b""


def test_connect_order_refund(connected: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, ORDER_REFUNDED)
    order = call(connected.connect.orders, "refund", ORDER_ID, idempotency_key="reembolso-1")
    assert order.status == "refunded"
    assert order.refunded_at == "2026-10-24T17:20:00Z"
    request = api.last
    assert (request.method, request.url.path) == (
        "POST",
        f"/v1/connect/orders/{ORDER_ID}/refund",
    )
    assert request.content == b""  # el reembolso va sin body
    assert "content-type" not in request.headers
    assert request.headers["content-length"] == "0"
    assert request.headers["idempotency-key"] == "reembolso-1"
    assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_connect_order_not_found(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(404, "ORDER_NOT_FOUND", "No encontramos ese pago.")
    with pytest.raises(rayacash.NotFoundError) as info:
        call(connected.connect.orders, "retrieve", PAYMENT_ID)
    assert info.value.code == "ORDER_NOT_FOUND"
    assert api.last.url.path == f"/v1/connect/orders/{PAYMENT_ID}"


def test_revoked_token_is_an_authentication_error(
    connected: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(
        401,
        "ACCESS_TOKEN_REVOKED",
        "La cuenta desconectó tu aplicación: el access_token ya no sirve.",
        headers={"WWW-Authenticate": 'Bearer realm="api"'},
    )
    with pytest.raises(rayacash.AuthenticationError) as info:
        call(connected.connect.orders, "retrieve", ORDER_ID)
    assert info.value.code == "ACCESS_TOKEN_REVOKED"
    assert info.value.headers["www-authenticate"] == 'Bearer realm="api"'
    assert len(api.requests) == 1


# --- Raya Connect: connect.payouts.*, con la clave secreta (no con el access_token) -------------


def test_connect_payout_create(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(201, PAYOUT_PENDING)
    payout = call(
        client.connect.payouts,
        "create",
        amount=Decimal("60000.00"),
        destination=PAYOUT_DESTINATION,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert type(payout) is rayacash.ConnectPayout
    assert payout.object == "connect.payout"
    assert payout.status == "pending"
    assert payout.amount == 60000
    assert payout.processing_fee == 870.25
    assert payout.net_amount == 59129.75
    assert payout.origin.account == PAYOUT_ORIGIN_ACCOUNT
    assert payout.origin.alias == "raya.cash.ejemplo"
    assert payout.origin.name == "Tienda Ejemplo"
    assert payout.counterparty.name == "Ana Ejemplo"
    assert payout.counterparty.tax_id == "20345678902"
    assert payout.counterparty.account == PAYOUT_DESTINATION
    assert payout.reference is None
    request = api.last
    assert (request.method, str(request.url)) == (
        "POST",
        "https://api.raya.cash/v1/connect/payouts",
    )
    # El body es exactamente amount y destination: la API rechaza cualquier otro parámetro.
    assert request.content == b'{"amount":60000,"destination":"0000123305838495183140"}'
    assert request.headers["content-type"] == "application/json"
    assert request.headers["idempotency-key"] == IDEMPOTENCY_KEY
    # Con la clave secreta, a diferencia de connect.orders: la plata sale de tu saldo.
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert payout.last_response is not None
    assert payout.last_response.idempotency_key == IDEMPOTENCY_KEY


@pytest.mark.parametrize(
    ("amount", "expected"),
    [(60000.5, b"60000.5"), ("60000.50", b"60000.5"), (Decimal("870.25"), b"870.25"), (1, b"1")],
)
def test_connect_payout_amount_forms(
    client: rayacash.RayaClient, api: MockAPI, amount: object, expected: bytes
) -> None:
    api.add(201, PAYOUT_PENDING)
    client.connect.payouts.create(amount=amount, destination="ana.ejemplo", idempotency_key="k")  # type: ignore[arg-type]
    assert api.last.content == b'{"amount":' + expected + b',"destination":"ana.ejemplo"}'


def test_connect_payout_create_requires_an_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    with pytest.raises(TypeError):
        client.connect.payouts.create(amount=1, destination="x")  # type: ignore[call-arg]
    with pytest.raises(TypeError, match=r"connect\.payouts\.create necesita idempotency_key"):
        client.connect.payouts.create(amount=1, destination="x", idempotency_key=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="idempotency_key"):
        client.connect.payouts.create(amount=1, destination="x", idempotency_key="con espacios")
    with pytest.raises(TypeError, match="destination"):
        client.connect.payouts.create(amount=1, destination=123, idempotency_key="k")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="amount"):
        client.connect.payouts.create(amount=True, destination="x", idempotency_key="k")
    assert api.requests == []


def test_connect_payout_create_takes_only_amount_and_destination(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    # El body de la API es exactamente {amount, destination}: un parámetro de más no existe.
    with pytest.raises(TypeError, match="external_reference"):
        client.connect.payouts.create(
            amount=1,
            destination="x",
            idempotency_key="k",
            external_reference="liquidacion-2087",  # type: ignore[call-arg]
        )
    assert api.requests == []


def test_connect_payout_retrieve(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, PAYOUT_COMPLETED)
    payout = call(client.connect.payouts, "retrieve", PAYOUT_ID)
    assert type(payout) is rayacash.ConnectPayout
    assert payout.status == "completed"
    assert payout.reference == "M7Q2X9T4K1V6N3B8R5W0ZD"
    request = api.last
    assert (request.method, request.url.path) == ("GET", f"/v1/connect/payouts/{PAYOUT_ID}")
    assert request.content == b""
    assert "idempotency-key" not in request.headers
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"


def test_connect_payout_list(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add(200, PAYOUT_LIST)
    page = call(
        client.connect.payouts,
        "list",
        status="completed",
        created_gte=datetime(2026, 10, 24, 3, tzinfo=timezone.utc),
        created_lt="2026-10-25T00:00:00-03:00",
        limit=10,
        cursor="c1",
    )
    assert type(page) is rayacash.ListObject
    assert [type(payout) for payout in page] == [rayacash.ConnectPayout]
    assert page.has_more is False
    assert page.data[0].status == "completed"
    request = api.last
    assert (request.method, request.url.path) == ("GET", "/v1/connect/payouts")
    assert dict(request.url.params) == {
        "status": "completed",
        "created_gte": "2026-10-24T03:00:00+00:00",
        "created_lt": "2026-10-25T00:00:00-03:00",
        "limit": "10",
        "cursor": "c1",
    }
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert "idempotency-key" not in request.headers


def test_connect_payout_list_without_filters(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(200, PAYOUT_LIST)
    client.connect.payouts.list()
    assert str(api.last.url) == "https://api.raya.cash/v1/connect/payouts"


def test_connect_payout_list_has_no_direction_filter(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    # Un payout siempre sale: direction (de transfers.list) no es un filtro de este endpoint.
    with pytest.raises(TypeError, match="direction"):
        client.connect.payouts.list(direction="outbound")  # type: ignore[call-arg]
    assert api.requests == []


def test_connect_payout_origin_unavailable(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(
        403,
        "PAYOUT_ORIGIN_UNAVAILABLE",
        "Para enviar payouts, primero configurá el descriptor del comercio en "
        "Configuración › Negocio.",
    )
    with pytest.raises(rayacash.PermissionDeniedError) as info:
        call(
            client.connect.payouts,
            "create",
            amount=60000,
            destination=PAYOUT_DESTINATION,
            idempotency_key=IDEMPOTENCY_KEY,
        )
    assert info.value.code == "PAYOUT_ORIGIN_UNAVAILABLE"
    assert info.value.http_status == 403
    assert info.value.data is None
    assert info.value.idempotency_key == IDEMPOTENCY_KEY
    assert len(api.requests) == 1  # los 4xx no se reintentan


def test_connect_payout_not_found(client: rayacash.RayaClient, api: MockAPI, call: Caller) -> None:
    api.add_error(404, "PAYOUT_NOT_FOUND", "No encontramos ese payout.")
    with pytest.raises(rayacash.NotFoundError) as info:
        call(client.connect.payouts, "retrieve", PAYMENT_ID)
    assert info.value.code == "PAYOUT_NOT_FOUND"
    assert info.value.http_status == 404
    assert info.value.message == "No encontramos ese payout."
    assert info.value.data is None
    assert api.last.url.path == f"/v1/connect/payouts/{PAYMENT_ID}"
    assert len(api.requests) == 1


def test_connect_payout_insufficient_balance_is_not_retried(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(422, "INSUFFICIENT_BALANCE", "El monto supera tu saldo disponible.")
    with pytest.raises(rayacash.UnprocessableEntityError) as info:
        call(client.connect.payouts, "create", amount=10**9, destination="x", idempotency_key="k")
    assert info.value.code == "INSUFFICIENT_BALANCE"
    assert info.value.idempotency_key == "k"
    assert len(api.requests) == 1


def test_connect_payout_create_retries_with_the_same_key(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    # Un corte en el medio no manda dos veces: el reintento lleva la misma Idempotency-Key.
    api.fail_with(httpx.ConnectError("cortado"))
    api.add(201, PAYOUT_PENDING)
    payout = call(
        client.connect.payouts,
        "create",
        amount=60000,
        destination=PAYOUT_DESTINATION,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    assert payout.status == "pending"
    assert [r.headers["idempotency-key"] for r in api.requests] == [IDEMPOTENCY_KEY] * 2


# --- Identidad: identity.verifications.*, con la clave secreta ---------------------------------

VERIFICATIONS_URL = "https://api.raya.cash/v1/identity/verifications"


def test_identity_verification_create(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(201, VERIFICATION_PENDING)
    verification = call(
        client.identity.verifications,
        "create",
        expires_in=86400,
        return_url="https://tienda.example.com/cuenta",
        metadata={"plan": "pro"},
        external_reference="cliente-8812",
        type="document",
    )
    assert type(verification) is rayacash.IdentityVerification
    assert verification.object == "identity.verification"
    assert verification.status == "pending"
    assert verification.url == f"https://raya.cash/identity/{VERIFICATION_ID}"
    request = api.last
    assert (request.method, str(request.url)) == ("POST", VERIFICATIONS_URL)
    # El body va en el orden del contrato (identity/api_params.py), no en el de los kwargs.
    assert request.content == (
        b'{"type":"document","external_reference":"cliente-8812","metadata":{"plan":"pro"},'
        b'"return_url":"https://tienda.example.com/cuenta","expires_in":86400}'
    )
    assert request.headers["content-type"] == "application/json"
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    # Sin clave propia, generamos un UUID v4 para esta llamada, como en payments.create.
    key = request.headers["idempotency-key"]
    assert uuid.UUID(key).version == 4
    assert verification.last_response is not None
    assert verification.last_response.idempotency_key == key
    assert verification.last_response.http_status == 201


def test_identity_verification_create_biometric_sends_its_reference(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(201, VERIFICATION_BIOMETRIC_VERIFIED)
    verification = call(
        client.identity.verifications, "create", type="biometric", reference=VERIFICATION_ID
    )
    assert api.last.content == b'{"type":"biometric","reference":"idv_3kT9vQ2mXw7Lp0aBcD4eF6gH"}'
    assert verification.id == BIOMETRIC_ID
    assert verification.type == "biometric"
    assert verification.reference == VERIFICATION_ID


def test_identity_verification_create_sends_only_what_you_pass(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(201, VERIFICATION_PENDING)
    call(
        client.identity.verifications,
        "create",
        type="document",
        external_reference=None,
        metadata=None,
        return_url=None,
        expires_in=None,
        reference=None,
        idempotency_key="alta-cliente-8812",
    )
    assert api.last.content == b'{"type":"document"}'
    assert api.last.headers["idempotency-key"] == "alta-cliente-8812"


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        (
            {"metadata": [("plan", "pro")]},
            TypeError,
            "^metadata tiene que ser un dict de str a str",
        ),
        ({"metadata": "plan=pro"}, TypeError, "^metadata tiene que ser un dict"),
        ({"metadata": {1: "pro"}}, TypeError, "tienen que ser str"),
        ({"expires_in": 86400.0}, TypeError, "^expires_in tiene que ser un int"),
        ({"expires_in": "86400"}, TypeError, "^expires_in tiene que ser un int"),
        ({"expires_in": True}, TypeError, "^expires_in tiene que ser un int"),
        ({"idempotency_key": "con espacios"}, ValueError, "^idempotency_key"),
        ({"idempotency_key": ""}, ValueError, "^idempotency_key"),
        ({"idempotency_key": 1234}, TypeError, "^idempotency_key"),
        # Un parámetro que no existe, y la idempotency key con el nombre de Node.js.
        ({"expires": 3600}, TypeError, "expires"),
        ({"idempotencyKey": "k"}, TypeError, "idempotencyKey"),
    ],
)
def test_identity_verification_create_rejects_bad_shapes_before_sending(
    client: rayacash.RayaClient,
    api: MockAPI,
    call: Caller,
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        call(client.identity.verifications, "create", type="document", **kwargs)
    assert api.requests == []


def test_identity_verification_create_leaves_the_rest_to_the_api(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    # Sin type (o un type que no existe) la request sale igual: la API responde con el campo.
    api.add_error(400, "PARAMETER_MISSING", "Falta el parámetro type.", {"field": "type"})
    with pytest.raises(rayacash.InvalidRequestError) as info:
        client.identity.verifications.create(type=None)  # type: ignore[arg-type]
    assert info.value.code == "PARAMETER_MISSING"
    assert info.value.param == "type"
    assert api.last.content == b"{}"
    api.add_error(
        400,
        "PARAMETER_INVALID",
        "reference solo se usa con type biometric.",
        {"field": "reference"},
    )
    with pytest.raises(rayacash.InvalidRequestError) as info:
        client.identity.verifications.create(type="document", reference=VERIFICATION_ID)
    assert info.value.param == "reference"
    assert api.last_json() == {"type": "document", "reference": VERIFICATION_ID}
    assert len(api.requests) == 2  # los 4xx no se reintentan


def test_identity_verification_retrieve(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(200, VERIFICATION_VERIFIED)
    verification = call(client.identity.verifications, "retrieve", VERIFICATION_ID)
    assert type(verification) is rayacash.IdentityVerification
    assert verification.status == "verified"
    assert verification.person is not None
    assert verification.person.first_name == "María Laura"
    assert verification.person.document["copy"] == "A"
    assert verification.checks.registry.face_match == "hit"
    assert verification.amount == 1000
    request = api.last
    assert (request.method, str(request.url)) == ("GET", f"{VERIFICATIONS_URL}/{VERIFICATION_ID}")
    assert request.content == b""
    assert "content-type" not in request.headers
    assert "idempotency-key" not in request.headers
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"


def test_identity_verification_declined_has_its_reason(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, VERIFICATION_DECLINED)
    verification = client.identity.verifications.retrieve(VERIFICATION_ID)
    assert verification.status == "declined"
    assert verification.decline_reason is not None
    assert verification.decline_reason.code == "registry_data_mismatch"
    assert verification.person is None
    assert verification.amount is None


def test_identity_verification_options_per_call(
    client: rayacash.RayaClient, api: MockAPI, sleeps: list[float]
) -> None:
    api.add_error(503, "TEMPORARILY_UNAVAILABLE", headers={"Retry-After": "5"})
    with pytest.raises(rayacash.APIError) as info:
        client.identity.verifications.retrieve(
            VERIFICATION_ID,
            options={"api_key": OTHER_KEY, "timeout": 10, "max_network_retries": 0},
        )
    assert info.value.code == "TEMPORARILY_UNAVAILABLE"
    assert api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert api.last.extensions["timeout"]["read"] == 10.0
    assert len(api.requests) == 1
    assert sleeps == []


@pytest.mark.parametrize("method", ["retrieve", "cancel", "files"])
@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "no puede estar vacío"),
        ("   ", "no puede estar vacío"),
        (".", r'no puede ser "\." ni "\.\."'),
        ("..", r'no puede ser "\." ni "\.\."'),
    ],
)
def test_identity_verification_ids_fail_before_sending(
    client: rayacash.RayaClient,
    api: MockAPI,
    call: Caller,
    method: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=rf"^verification_id {message}\.$"):
        call(client.identity.verifications, method, value)
    assert api.requests == []


def test_identity_verification_ids_are_strings_and_are_encoded(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    for method in ("retrieve", "cancel", "files"):
        with pytest.raises(TypeError, match=r"^verification_id tiene que ser un str, no int\.$"):
            call(client.identity.verifications, method, 1234)
    assert api.requests == []
    api.add(200, VERIFICATION_PENDING)
    call(client.identity.verifications, "retrieve", "../cancel")
    assert api.last.url.raw_path == b"/v1/identity/verifications/..%2Fcancel"
    api.add(200, VERIFICATION_CANCELED)
    call(client.identity.verifications, "cancel", "idv_x/../files")
    assert api.last.url.raw_path == b"/v1/identity/verifications/idv_x%2F..%2Ffiles/cancel"


def test_identity_verification_list(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(200, VERIFICATION_LIST)
    page = call(
        client.identity.verifications,
        "list",
        cursor="c1",
        limit=50,
        created_lt="2026-10-25T00:00:00-03:00",
        created_gte=datetime(2026, 11, 10, 3, tzinfo=timezone.utc),
        external_reference="cliente 8812",
        type="document",
        status="verified",
    )
    assert type(page) is rayacash.ListObject
    assert [type(verification) for verification in page] == [rayacash.IdentityVerification] * 2
    assert page.data[0].id == BIOMETRIC_ID
    assert page.has_more is True
    assert page.next_cursor == NEXT_CURSOR
    request = api.last
    assert (request.method, request.url.path) == ("GET", "/v1/identity/verifications")
    # La query exacta: en el orden del contrato, y el datetime en ISO 8601 con su zona.
    assert request.url.query == (
        b"status=verified&type=document&external_reference=cliente+8812"
        b"&created_gte=2026-11-10T03%3A00%3A00%2B00%3A00"
        b"&created_lt=2026-10-25T00%3A00%3A00-03%3A00&limit=50&cursor=c1"
    )
    assert dict(request.url.params) == {
        "status": "verified",
        "type": "document",
        "external_reference": "cliente 8812",
        "created_gte": "2026-11-10T03:00:00+00:00",
        "created_lt": "2026-10-25T00:00:00-03:00",
        "limit": "50",
        "cursor": "c1",
    }
    assert request.content == b""
    assert "idempotency-key" not in request.headers


def test_identity_verification_list_without_filters(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, {**VERIFICATION_LIST, "has_more": False, "next_cursor": None})
    client.identity.verifications.list()
    assert str(api.last.url) == VERIFICATIONS_URL


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"created_gte": datetime(2026, 11, 10)}, ValueError, "^created_gte necesita zona"),
        ({"created_lt": datetime(2026, 11, 11)}, ValueError, "^created_lt necesita zona"),
        ({"status": True}, TypeError, "^status no puede ser un bool"),
        ({"limit": 1.5}, TypeError, "^limit no acepta un float"),
        ({"limit": True}, TypeError, "^limit no puede ser un bool"),
        ({"type": ["document"]}, TypeError, "^type no acepta un list"),
        # Un filtro que no existe (direction es de transfers.list).
        ({"estado": "verified"}, TypeError, "estado"),
        ({"direction": "inbound"}, TypeError, "direction"),
    ],
)
def test_identity_verification_list_rejects_bad_filters_before_sending(
    client: rayacash.RayaClient,
    api: MockAPI,
    call: Caller,
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        call(client.identity.verifications, "list", **kwargs)
    assert api.requests == []


def test_identity_verification_cancel(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(200, VERIFICATION_CANCELED)
    verification = call(client.identity.verifications, "cancel", VERIFICATION_ID)
    assert type(verification) is rayacash.IdentityVerification
    assert verification.status == "canceled"
    request = api.last
    assert (request.method, str(request.url)) == (
        "POST",
        f"{VERIFICATIONS_URL}/{VERIFICATION_ID}/cancel",
    )
    assert request.content == b""  # cancelar va sin body
    assert "content-type" not in request.headers
    assert request.headers["content-length"] == "0"
    key = request.headers["idempotency-key"]
    assert uuid.UUID(key).version == 4
    assert verification.last_response is not None
    assert verification.last_response.idempotency_key == key


def test_identity_verification_cancel_with_your_key(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(200, VERIFICATION_CANCELED)
    verification = call(
        client.identity.verifications, "cancel", VERIFICATION_ID, idempotency_key="cancelar-8812"
    )
    assert api.last.headers["idempotency-key"] == "cancelar-8812"
    assert verification.last_response.idempotency_key == "cancelar-8812"
    with pytest.raises(ValueError, match=r"^idempotency_key tiene que tener de 1 a 255"):
        call(
            client.identity.verifications, "cancel", VERIFICATION_ID, idempotency_key="con espacios"
        )
    assert len(api.requests) == 1


def test_identity_verification_files(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add(200, VERIFICATION_FILES)
    files = call(client.identity.verifications, "files", VERIFICATION_ID)
    assert type(files) is rayacash.IdentityVerificationFiles
    assert files.object == "identity.verification_files"
    assert type(files.front) is rayacash.IdentityVerificationFiles.File
    assert files.front.url == VERIFICATION_FILES["front"]["url"]
    assert files.selfie is not None
    assert files.selfie.expires_at == "2026-10-24T18:25:00Z"
    request = api.last
    assert (request.method, str(request.url)) == (
        "GET",
        f"{VERIFICATIONS_URL}/{VERIFICATION_ID}/files",
    )
    assert request.content == b""
    assert "idempotency-key" not in request.headers


def test_identity_verification_gets_take_no_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    verifications: Any = client.identity.verifications  # llamadas que el type checker ya rechaza
    for method in ("retrieve", "files"):
        with pytest.raises(TypeError, match="idempotency_key"):
            getattr(verifications, method)(VERIFICATION_ID, idempotency_key="k")
    assert api.requests == []


def test_identity_verification_each_post_without_a_key_gets_its_own(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    # Una clave por llamada (no por cliente ni por proceso): dos altas iguales son dos altas.
    for _ in range(2):
        api.add(201, VERIFICATION_PENDING)
        call(client.identity.verifications, "create", type="document")
    for _ in range(2):
        api.add(200, VERIFICATION_CANCELED)
        call(client.identity.verifications, "cancel", VERIFICATION_ID)
    keys = [request.headers["idempotency-key"] for request in api.requests]
    assert len(set(keys)) == 4
    assert all(uuid.UUID(key).version == 4 for key in keys)


def test_identity_verification_create_retries_with_the_same_key(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    # La clave que generamos se reusa en el reintento: un corte nunca crea dos verificaciones.
    api.fail_with(httpx.ConnectError("cortado"))
    api.add(201, VERIFICATION_PENDING)
    verification = call(client.identity.verifications, "create", type="document")
    keys = [request.headers["idempotency-key"] for request in api.requests]
    assert len(keys) == 2
    assert keys[0] == keys[1]
    assert verification.last_response.idempotency_key == keys[0]


def test_identity_verification_not_found(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    api.add_error(404, "VERIFICATION_NOT_FOUND", "No encontramos esa verificación.")
    with pytest.raises(rayacash.NotFoundError) as info:
        call(client.identity.verifications, "retrieve", VERIFICATION_ID)
    assert info.value.code == "VERIFICATION_NOT_FOUND"
    assert info.value.http_status == 404
    assert info.value.message == "No encontramos esa verificación."
    assert info.value.request_id == "req_test00000000000000000001"
    assert info.value.data is None
    assert len(api.requests) == 1


def test_identity_verification_not_cancelable(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    api.add_error(
        409,
        "VERIFICATION_NOT_CANCELABLE",
        "Solo podés cancelar verificaciones pending o in_progress.",
        {"status": "processing"},
    )
    with pytest.raises(rayacash.ConflictError) as info:
        call(client.identity.verifications, "cancel", VERIFICATION_ID, idempotency_key="c-1")
    assert type(info.value) is rayacash.ConflictError  # no es un IdempotencyError
    assert info.value.code == "VERIFICATION_NOT_CANCELABLE"
    assert info.value.data == {"status": "processing"}
    assert info.value.idempotency_key == "c-1"
    assert len(api.requests) == 1  # no se reintenta
    assert sleeps == []


def test_identity_verification_limit_is_not_retried(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    # El tope de verificaciones de la cuenta: 429 con Retry-After: 3600, más de lo que esperamos.
    api.add_error(
        429,
        "RATE_LIMITED",
        "Llegaste al máximo de verificaciones por día.",
        {"limit": "daily"},
        headers={"Retry-After": "3600"},
    )
    with pytest.raises(rayacash.RateLimitError) as info:
        call(client.identity.verifications, "create", type="document")
    assert info.value.retry_after == 3600
    assert info.value.data == {"limit": "daily"}
    assert len(api.requests) == 1
    assert sleeps == []


def test_identity_is_not_available_in_the_sandbox_yet(api: MockAPI, call: Caller) -> None:
    # Una clave de prueba llega a la API, que responde 403: Identidad todavía no está disponible
    # en el sandbox.
    client = api.client(SANDBOX_KEY)
    api.add_error(
        403,
        "SANDBOX_NOT_SUPPORTED",
        "Este endpoint todavía no está disponible en un sandbox.",
    )
    with pytest.raises(rayacash.PermissionDeniedError) as info:
        call(client.identity.verifications, "create", type="document")
    assert info.value.code == "SANDBOX_NOT_SUPPORTED"
    assert info.value.http_status == 403
    assert len(api.requests) == 1


# --- Sandbox: test_helpers.payments.simulate_transfer, con la clave secreta de prueba ----------

SIMULATE_PATH = f"/v1/test/payments/{SANDBOX_PAYMENT_ID}/simulate_transfer"
NOT_PENDING_MESSAGE = "Solo podés simular la transferencia de un pago pendiente."


def test_simulate_transfer(api: MockAPI, call: Caller) -> None:
    sandbox = api.client(SANDBOX_KEY)
    api.add(200, SANDBOX_PAYMENT_SUCCEEDED)
    payment = call(sandbox.test_helpers.payments, "simulate_transfer", SANDBOX_PAYMENT_ID)
    assert type(payment) is rayacash.Payment
    assert payment.status == "succeeded"
    assert payment.amount_received == payment.amount == 2500
    assert payment.payer is not None
    assert payment.payer.name == "Pagador de prueba"  # siempre el mismo
    assert payment.bank_transfer.cvu.startswith("00000002")
    assert payment.bank_transfer.alias == "sandbox.no.transferir"
    assert payment.checkout_url == f"https://raya.cash/sandbox/pay/{SANDBOX_PAYMENT_ID}"
    request = api.last
    assert (request.method, str(request.url)) == ("POST", "https://api.raya.cash" + SIMULATE_PATH)
    # Sin amount no va body, como en un reembolso: el monto exacto del pago.
    assert request.content == b""
    assert "content-type" not in request.headers
    assert request.headers["content-length"] == "0"
    assert request.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    # Sin Idempotency-Key: el endpoint no la usa (simular otra vez responde PAYMENT_NOT_PENDING).
    assert "idempotency-key" not in request.headers
    assert payment.last_response is not None
    assert payment.last_response.idempotency_key is None
    assert payment.last_response.request_id == "req_test00000000000000000001"


def test_simulate_transfer_with_another_amount(api: MockAPI, call: Caller) -> None:
    sandbox = api.client(SANDBOX_KEY)
    # Menos que el pago: failed con amount_mismatch (en un sandbox no se devuelve solo).
    api.add(200, SANDBOX_PAYMENT_FAILED)
    payment = call(
        sandbox.test_helpers.payments, "simulate_transfer", SANDBOX_PAYMENT_ID, amount=1000
    )
    assert type(payment) is rayacash.Payment
    assert payment.status == "failed"
    assert payment.failure_code == "amount_mismatch"
    assert payment.amount_received == 1000
    assert payment.paid_at is None
    assert api.last.content == b'{"amount":1000}'
    assert api.last.headers["content-type"] == "application/json"
    assert "idempotency-key" not in api.last.headers
    # Más que el pago: succeeded, con amount_received en lo simulado.
    api.add(200, SANDBOX_PAYMENT_OVERPAID)
    payment = call(
        sandbox.test_helpers.payments,
        "simulate_transfer",
        SANDBOX_PAYMENT_ID,
        amount=Decimal("4000.00"),
    )
    assert payment.status == "succeeded"
    assert payment.amount_received == 4000
    assert api.last.content == b'{"amount":4000}'
    assert "idempotency-key" not in api.last.headers


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1000, b"1000"),
        (1000.5, b"1000.5"),
        (Decimal("1000.50"), b"1000.5"),
        ("1000.50", b"1000.5"),
        (None, None),
    ],
)
def test_simulate_transfer_amount_forms(
    api: MockAPI, amount: rayacash.Amount | None, expected: bytes | None
) -> None:
    api.add(200, SANDBOX_PAYMENT_FAILED)
    api.client(SANDBOX_KEY).test_helpers.payments.simulate_transfer(
        SANDBOX_PAYMENT_ID, amount=amount
    )
    # Un número JSON exacto, como el amount de payments.create. Con None, sin body.
    assert api.last.content == (b'{"amount":' + expected + b"}" if expected else b"")


def test_simulate_transfer_of_a_connect_order(api: MockAPI, call: Caller) -> None:
    # El id de una orden de una app del sandbox, con la clave secreta de prueba de la cuenta dueña
    # de la app (no con el access_token del usuario de prueba): vuelve el connect.order.
    sandbox = api.client(SANDBOX_KEY)
    api.add(200, SANDBOX_ORDER_SUCCEEDED)
    order = call(sandbox.test_helpers.payments, "simulate_transfer", SANDBOX_ORDER_ID)
    assert type(order) is rayacash.ConnectOrder
    assert order.object == "connect.order"
    assert order.status == "succeeded"
    assert (order.fee, order.net_amount) == (10, 1490)
    assert type(order["items"][0]) is rayacash.ConnectOrder.Item
    request = api.last
    assert (request.method, request.url.path) == (
        "POST",
        f"/v1/test/payments/{SANDBOX_ORDER_ID}/simulate_transfer",
    )
    assert request.content == b""
    assert request.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    assert "idempotency-key" not in request.headers


def test_simulate_transfer_of_a_payment_that_is_not_pending(
    api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    api.add_error(409, "PAYMENT_NOT_PENDING", NOT_PENDING_MESSAGE, {"status": "succeeded"})
    with pytest.raises(rayacash.ConflictError) as info:
        call(api.client(SANDBOX_KEY).test_helpers.payments, "simulate_transfer", SANDBOX_PAYMENT_ID)
    assert type(info.value) is rayacash.ConflictError  # no es un IdempotencyError
    assert info.value.code == "PAYMENT_NOT_PENDING"
    assert info.value.http_status == 409
    assert info.value.message == NOT_PENDING_MESSAGE
    assert info.value.data == {"status": "succeeded"}
    assert info.value.idempotency_key is None
    assert len(api.requests) == 1  # no se reintenta
    assert sleeps == []


def test_simulate_transfer_of_an_unknown_payment(api: MockAPI, call: Caller) -> None:
    # Un id de otro sandbox, de un pago real o que no existe: los tres dan lo mismo.
    api.add_error(404, "PAYMENT_NOT_FOUND", "No encontramos ese pago.")
    with pytest.raises(rayacash.NotFoundError) as info:
        call(api.client(SANDBOX_KEY).test_helpers.payments, "simulate_transfer", PAYMENT_ID)
    assert info.value.code == "PAYMENT_NOT_FOUND"
    assert info.value.http_status == 404
    assert info.value.data is None
    assert api.last.url.path == f"/v1/test/payments/{PAYMENT_ID}/simulate_transfer"
    assert len(api.requests) == 1


def test_simulate_transfer_with_a_real_key_is_sandbox_only(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    # El SDK no decide por la clave: la manda, y la API responde que el helper es solo del sandbox.
    message = "Este endpoint solo funciona en un sandbox: usá una credencial de prueba."
    api.add_error(403, "SANDBOX_ONLY", message)
    with pytest.raises(rayacash.PermissionDeniedError) as info:
        call(client.test_helpers.payments, "simulate_transfer", PAYMENT_ID)
    assert info.value.code == "SANDBOX_ONLY"
    assert info.value.http_status == 403
    assert info.value.message == message
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert len(api.requests) == 1


def test_simulate_transfer_retries_a_cut_without_an_idempotency_key(
    api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    # Sin Idempotency-Key, un corte igual se reintenta. Si el primer intento llegó y simuló, el
    # reintento responde PAYMENT_NOT_PENDING: el pago nunca se simula dos veces.
    api.fail_with(httpx.ReadTimeout("lento"))
    api.add_error(409, "PAYMENT_NOT_PENDING", NOT_PENDING_MESSAGE, {"status": "succeeded"})
    with pytest.raises(rayacash.ConflictError) as info:
        call(api.client(SANDBOX_KEY).test_helpers.payments, "simulate_transfer", SANDBOX_PAYMENT_ID)
    assert info.value.code == "PAYMENT_NOT_PENDING"
    assert info.value.idempotency_key is None
    assert len(api.requests) == 2
    assert all("idempotency-key" not in request.headers for request in api.requests)
    assert sleeps == [0.5]


def test_simulate_transfer_connection_errors_promise_no_idempotency_key(api: MockAPI) -> None:
    for _ in range(3):
        api.fail_with(httpx.ConnectError("sin red"))
    with pytest.raises(rayacash.APIConnectionError) as info:
        api.client(SANDBOX_KEY).test_helpers.payments.simulate_transfer(SANDBOX_PAYMENT_ID)
    assert info.value.code == "NETWORK_ERROR"
    assert info.value.idempotency_key is None
    assert "Idempotency-Key" not in info.value.message
    assert len(api.requests) == 3


def test_simulate_transfer_rejects_bad_input_before_sending(api: MockAPI, call: Caller) -> None:
    payments = api.client(SANDBOX_KEY).test_helpers.payments
    with pytest.raises(ValueError, match=r"^payment_id no puede estar vacío"):
        call(payments, "simulate_transfer", " ")
    for value in (".", ".."):
        with pytest.raises(ValueError, match=r'^payment_id no puede ser "\." ni "\.\."\.$'):
            call(payments, "simulate_transfer", value)
    with pytest.raises(TypeError, match=r"^payment_id tiene que ser un str"):
        call(payments, "simulate_transfer", None)
    with pytest.raises(TypeError, match=r"^amount no puede ser un bool"):
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID, amount=True)
    with pytest.raises(ValueError, match=r"^amount 'mil' no es un número"):
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID, amount="mil")
    with pytest.raises(ValueError, match=r"^amount tiene que ser un número finito"):
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID, amount=float("nan"))
    # Sin idempotency_key: ni como parámetro ni en options.
    with pytest.raises(TypeError, match="idempotency_key"):
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID, idempotency_key="k")
    with pytest.raises(TypeError, match="idempotency_key"):
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID, options={"idempotency_key": "k"})
    assert api.requests == []


def test_simulate_transfer_encodes_the_id(api: MockAPI) -> None:
    api.add_error(404, "PAYMENT_NOT_FOUND", "No encontramos ese pago.")
    with pytest.raises(rayacash.NotFoundError):
        api.client(SANDBOX_KEY).test_helpers.payments.simulate_transfer("../balance")
    assert api.last.url.raw_path == b"/v1/test/payments/..%2Fbalance/simulate_transfer"


def test_simulate_transfer_with_the_key_per_call(client: rayacash.RayaClient, api: MockAPI) -> None:
    # Un cliente con la clave real puede pasar la de prueba para una sola llamada.
    api.add(200, SANDBOX_PAYMENT_SUCCEEDED)
    client.test_helpers.payments.simulate_transfer(
        SANDBOX_PAYMENT_ID, options={"api_key": SANDBOX_KEY, "timeout": 10}
    )
    assert api.last.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    assert api.last.extensions["timeout"]["read"] == 10.0
    assert "idempotency-key" not in api.last.headers


def test_simulate_transfer_needs_a_payment_or_an_order(api: MockAPI, call: Caller) -> None:
    api.add(200, BALANCE)
    payments = api.client(SANDBOX_KEY).test_helpers.payments
    with pytest.raises(rayacash.APIError, match="no es un Payment ni un ConnectOrder") as info:
        call(payments, "simulate_transfer", SANDBOX_PAYMENT_ID)
    # Con la respuesta, como todo error de la API.
    error = info.value
    assert error.code == "INVALID_RESPONSE"
    assert error.http_status == 200
    assert error.request_id == "req_test00000000000000000001"
    assert error.headers["raya-request-id"] == error.request_id
    assert error.http_body is not None
    assert json.loads(error.http_body) == BALANCE
    assert error.idempotency_key is None
    assert len(api.requests) == 1


def test_simulate_transfer_without_object_is_a_payment(api: MockAPI) -> None:
    # La clase sale de object; sin object, Payment es el respaldo (como en los otros SDKs).
    body = {key: value for key, value in SANDBOX_PAYMENT_SUCCEEDED.items() if key != "object"}
    api.add(200, body)
    payment = api.client(SANDBOX_KEY).test_helpers.payments.simulate_transfer(SANDBOX_PAYMENT_ID)
    assert type(payment) is rayacash.Payment
    assert payment.to_dict() == body
