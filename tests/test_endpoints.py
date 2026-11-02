"""Los 7 endpoints, en sync y en async: método, ruta, query, body y headers exactos."""

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
