"""El estilo global: rayacash.api_key + rayacash.Payment.create(...)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import rayacash
from rayacash._requestor import HTTPClientManager
from tests.fixtures import (
    BALANCE,
    EVENT_PAYMENT_SUCCEEDED,
    PAYMENT_ID,
    PAYMENT_PENDING,
    PAYMENT_REFUNDED,
    PAYMENT_SUCCEEDED,
    TRANSFER_INBOUND,
    TRANSFER_LIST,
    TRANSFER_OUTBOUND_PENDING,
    WEBHOOK_SECRET,
)
from tests.helpers import OTHER_KEY, TEST_KEY, Caller, MockAPI


@pytest.fixture
def global_api(api: MockAPI) -> MockAPI:
    rayacash.api_key = TEST_KEY
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    return api


def test_every_endpoint(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    api.add(200, BALANCE)
    assert type(call(rayacash.Balance, "retrieve")) is rayacash.Balance
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"

    api.add(201, TRANSFER_OUTBOUND_PENDING)
    transfer = call(
        rayacash.Transfer,
        "create",
        amount=25000,
        destination="proveedor.ejemplo",
        idempotency_key="k",
    )
    assert type(transfer) is rayacash.Transfer
    assert api.last.headers["idempotency-key"] == "k"

    api.add(200, TRANSFER_INBOUND)
    assert call(rayacash.Transfer, "retrieve", TRANSFER_INBOUND["id"]).direction == "inbound"

    api.add(200, TRANSFER_LIST)
    page = call(rayacash.Transfer, "list", direction="inbound", limit=2)
    assert type(page) is rayacash.ListObject
    assert api.last.url.params["limit"] == "2"

    api.add(201, PAYMENT_PENDING)
    payment = call(rayacash.Payment, "create", amount=15000, metadata={"cliente_id": "8812"})
    assert type(payment) is rayacash.Payment
    assert json.loads(api.last.content) == {"amount": 15000, "metadata": {"cliente_id": "8812"}}

    api.add(200, PAYMENT_SUCCEEDED)
    assert call(rayacash.Payment, "retrieve", PAYMENT_ID).status == "succeeded"

    api.add(200, PAYMENT_REFUNDED)
    assert call(rayacash.Payment, "refund", PAYMENT_ID, idempotency_key="r-1").status == "refunded"
    assert api.last.url.path == f"/v1/payments/{PAYMENT_ID}/refund"
    assert api.last.headers["idempotency-key"] == "r-1"


def test_instance_refund(global_api: MockAPI, call: Caller) -> None:
    global_api.add(200, PAYMENT_SUCCEEDED)
    payment = rayacash.Payment.retrieve(PAYMENT_ID)
    global_api.add(200, PAYMENT_REFUNDED)
    refunded = call(payment, "refund")
    assert refunded.status == "refunded"
    assert payment.status == "succeeded"  # devuelve un pago nuevo, no muta el original
    assert global_api.last.url.path == f"/v1/payments/{PAYMENT_ID}/refund"


def test_instance_refund_uses_the_client_it_came_from(global_api: MockAPI, call: Caller) -> None:
    other_api = MockAPI()
    client = other_api.client(OTHER_KEY)
    other_api.add(200, PAYMENT_SUCCEEDED)
    payment = client.payments.retrieve(PAYMENT_ID)
    other_api.add(200, PAYMENT_REFUNDED)
    call(payment, "refund")
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert global_api.requests == []


def test_events_from_webhook_construct_event_use_the_global_style(global_api: MockAPI) -> None:
    body = json.dumps(EVENT_PAYMENT_SUCCEEDED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    payment = event.data.object
    assert isinstance(payment, rayacash.Payment)
    global_api.add(200, PAYMENT_REFUNDED)
    asyncio.run(payment.refund_async(idempotency_key="r-2"))
    assert global_api.last.headers["idempotency-key"] == "r-2"


def test_refund_needs_an_id() -> None:
    payment = rayacash.Payment.construct_from({"object": "payment"})
    with pytest.raises(ValueError, match="no tiene id"):
        payment.refund()


def test_key_from_environment_and_changes_between_calls(
    api: MockAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    rayacash.http_client = api.sync_client()
    monkeypatch.setenv("RAYA_SECRET_KEY", OTHER_KEY)
    api.add(200, BALANCE)
    rayacash.Balance.retrieve()
    assert api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"

    rayacash.api_key = TEST_KEY  # gana sobre la variable de entorno
    api.add(200, BALANCE)
    rayacash.Balance.retrieve()
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"


def test_missing_key(api: MockAPI) -> None:
    rayacash.http_client = api.sync_client()
    with pytest.raises(rayacash.AuthenticationError) as info:
        rayacash.Balance.retrieve()
    assert info.value.code == "API_KEY_MISSING"
    assert api.requests == []


def test_global_settings(global_api: MockAPI, sleeps: list[float]) -> None:
    rayacash.api_base = "http://localhost:8000/"
    rayacash.timeout = 12
    rayacash.max_network_retries = 0
    rayacash.set_app_info("mi-plugin", version="2.0.0", url="https://plugin.example")
    global_api.add_error(500, "INTERNAL_ERROR")
    with pytest.raises(rayacash.APIError):
        rayacash.Balance.retrieve()
    request = global_api.last
    assert str(request.url) == "http://localhost:8000/v1/balance"
    assert request.extensions["timeout"]["read"] == 12.0
    assert request.headers["user-agent"].endswith(" mi-plugin/2.0.0 (https://plugin.example)")
    assert len(global_api.requests) == 1
    assert sleeps == []

    rayacash.set_app_info("solo")
    assert rayacash.app_info == {"name": "solo"}
    rayacash.api_base = "http://inseguro.example"
    with pytest.raises(ValueError, match="api_base"):
        rayacash.Balance.retrieve()


def test_swapping_the_global_http_client(api: MockAPI) -> None:
    rayacash.api_key = TEST_KEY
    rayacash.http_client = api.sync_client()
    api.add(200, BALANCE)
    rayacash.Balance.retrieve()

    other = MockAPI()
    rayacash.http_client = other.sync_client()
    other.add(200, BALANCE)
    rayacash.Balance.retrieve()
    assert len(api.requests) == 1
    assert len(other.requests) == 1


def test_owned_global_clients(monkeypatch: pytest.MonkeyPatch, api: MockAPI) -> None:
    created: list[httpx.Client] = []

    def new_client(self: HTTPClientManager) -> httpx.Client:
        created.append(api.sync_client())
        return created[-1]

    monkeypatch.setattr(HTTPClientManager, "_new_sync_client", new_client)
    rayacash.api_key = TEST_KEY
    api.add(200, BALANCE)
    api.add(200, BALANCE)
    rayacash.Balance.retrieve()
    rayacash.Balance.retrieve()
    assert len(created) == 1  # el estilo global reusa su cliente httpx
