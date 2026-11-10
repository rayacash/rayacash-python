"""Los 12 endpoints, en sync y en async: método, ruta, query, body y headers exactos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

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
    REDIRECT_URI,
    USER,
    USER_ID,
)
from tests.helpers import Caller, MockAPI

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
