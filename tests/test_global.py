"""El estilo global: rayacash.api_key + rayacash.Payment.create(...)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx
import pytest

import rayacash
from rayacash._requestor import HTTPClientManager
from tests import fixtures_facturador as facturador
from tests import fixtures_psp as psp
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
from tests.fixtures_apps import (
    ACCESS_TOKEN,
    APP_CLIENT_ID,
    APP_CLIENT_SECRET,
    AUTH_CODE,
    EVENT_ORDER_SUCCEEDED,
    OAUTH_TOKEN,
    ORDER_ID,
    ORDER_PENDING,
    ORDER_REFUNDED,
    ORDER_SUCCEEDED,
    PAYOUT_COMPLETED,
    PAYOUT_DESTINATION,
    PAYOUT_ID,
    PAYOUT_LIST,
    PAYOUT_PENDING,
    REDIRECT_URI,
    USER,
    USER_ID,
)
from tests.fixtures_identity import (
    EVENT_VERIFICATION_VERIFIED,
    VERIFICATION_CANCELED,
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
)
from tests.helpers import OTHER_KEY, TEST_KEY, Caller, MockAPI

ITEM = {"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}


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


def test_global_api_base_without_the_empty_query_or_fragment(global_api: MockAPI) -> None:
    rayacash.api_base = "https://api.raya.cash/?#"
    global_api.add(200, BALANCE)
    rayacash.Balance.retrieve()
    assert str(global_api.last.url) == "https://api.raya.cash/v1/balance"


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


# --- Raya Connect: rayacash.OAuth / User / ConnectOrder ------------------------------------------


def test_apps_endpoints(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    api.add(200, OAUTH_TOKEN)
    token = call(rayacash.OAuth, "token", APP_CLIENT_ID, APP_CLIENT_SECRET, AUTH_CODE, REDIRECT_URI)
    assert type(token) is rayacash.OAuthToken
    assert "authorization" not in api.last.headers
    assert json.loads(api.last.content)["grant_type"] == "authorization_code"

    rayacash.api_key = token.access_token  # el estilo global opera por la cuenta conectada
    api.add(200, USER)
    user = call(rayacash.User, "retrieve", token.user_id)
    assert type(user) is rayacash.User
    assert api.last.url.path == f"/v1/users/{USER_ID}"
    assert api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"

    api.add(201, ORDER_PENDING)
    order = call(rayacash.ConnectOrder, "create", items=[ITEM], fee=500)
    assert type(order) is rayacash.ConnectOrder
    assert api.last.url.path == "/v1/connect/orders"
    assert json.loads(api.last.content) == {"items": [ITEM], "fee": 500}
    assert uuid.UUID(api.last.headers["idempotency-key"]).version == 4

    api.add(200, ORDER_SUCCEEDED)
    assert call(rayacash.ConnectOrder, "retrieve", ORDER_ID).status == "succeeded"
    assert api.last.url.path == f"/v1/connect/orders/{ORDER_ID}"

    api.add(200, ORDER_REFUNDED)
    refunded = call(rayacash.ConnectOrder, "refund", ORDER_ID, idempotency_key="r-1")
    assert refunded.status == "refunded"
    assert api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"
    assert api.last.headers["idempotency-key"] == "r-1"


def test_oauth_token_without_any_key(api: MockAPI, call: Caller) -> None:
    # Sin rayacash.api_key ni RAYA_SECRET_KEY: el canje no necesita clave.
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    api.add(200, OAUTH_TOKEN)
    token = call(rayacash.OAuth, "token", APP_CLIENT_ID, APP_CLIENT_SECRET, AUTH_CODE, REDIRECT_URI)
    assert token.user_id == USER_ID
    assert "authorization" not in api.last.headers
    assert "idempotency-key" not in api.last.headers


def test_connect_order_instance_refund(global_api: MockAPI, call: Caller) -> None:
    rayacash.api_key = ACCESS_TOKEN
    global_api.add(200, ORDER_SUCCEEDED)
    order = rayacash.ConnectOrder.retrieve(ORDER_ID)
    global_api.add(200, ORDER_REFUNDED)
    refunded = call(order, "refund")
    assert refunded.status == "refunded"
    assert order.status == "succeeded"  # devuelve un pago nuevo, no muta el original
    assert global_api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"
    assert global_api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_connect_order_instance_refund_uses_the_client_it_came_from(
    global_api: MockAPI, call: Caller
) -> None:
    other_api = MockAPI()
    connected = other_api.client(ACCESS_TOKEN)
    other_api.add(200, ORDER_SUCCEEDED)
    order = connected.connect.orders.retrieve(ORDER_ID)
    other_api.add(200, ORDER_REFUNDED)
    call(order, "refund", idempotency_key="r-3")
    assert other_api.last.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert other_api.last.headers["idempotency-key"] == "r-3"
    assert global_api.requests == []


def test_connect_order_events_from_construct_event_use_the_global_style(
    global_api: MockAPI,
) -> None:
    # Un connect.order.succeeded firmado, de punta a punta: el tipo y el object llevan puntos.
    body = json.dumps(EVENT_ORDER_SUCCEEDED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert event.type == "connect.order.succeeded"
    order = event.data.object
    assert isinstance(order, rayacash.ConnectOrder)
    global_api.add(200, ORDER_REFUNDED)
    asyncio.run(order.refund_async(idempotency_key="r-2"))
    assert global_api.last.url.path == f"/v1/connect/orders/{ORDER_ID}/refund"
    assert global_api.last.headers["idempotency-key"] == "r-2"


def test_connect_order_refund_needs_an_id() -> None:
    order = rayacash.ConnectOrder.construct_from({"object": "connect.order"})
    with pytest.raises(ValueError, match="no tiene id"):
        order.refund()


# --- Raya Connect: rayacash.ConnectPayout, con la clave secreta --------------------------------


def test_connect_payout_endpoints(global_api: MockAPI, call: Caller) -> None:
    api = global_api  # rayacash.api_key es la clave secreta, no un access_token
    api.add(201, PAYOUT_PENDING)
    payout = call(
        rayacash.ConnectPayout,
        "create",
        amount=60000,
        destination=PAYOUT_DESTINATION,
        idempotency_key="k",
    )
    assert type(payout) is rayacash.ConnectPayout
    assert payout.net_amount == 59129.75
    assert api.last.url.path == "/v1/connect/payouts"
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert api.last.headers["idempotency-key"] == "k"
    assert json.loads(api.last.content) == {"amount": 60000, "destination": PAYOUT_DESTINATION}

    api.add(200, PAYOUT_COMPLETED)
    assert call(rayacash.ConnectPayout, "retrieve", PAYOUT_ID).status == "completed"
    assert api.last.url.path == f"/v1/connect/payouts/{PAYOUT_ID}"

    api.add(200, PAYOUT_LIST)
    page = call(rayacash.ConnectPayout, "list", status="completed", limit=2)
    assert type(page) is rayacash.ListObject
    assert type(page.data[0]) is rayacash.ConnectPayout
    assert api.last.url.path == "/v1/connect/payouts"
    assert dict(api.last.url.params) == {"status": "completed", "limit": "2"}


# --- Identidad: rayacash.IdentityVerification, con la clave secreta -----------------------------

VERIFICATION_PATH = f"/v1/identity/verifications/{VERIFICATION_ID}"


def test_identity_verification_endpoints(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    api.add(201, VERIFICATION_PENDING)
    verification = call(
        rayacash.IdentityVerification,
        "create",
        type="document",
        metadata={"plan": "pro"},
        idempotency_key="k",
    )
    assert type(verification) is rayacash.IdentityVerification
    assert api.last.url.path == "/v1/identity/verifications"
    assert json.loads(api.last.content) == {"type": "document", "metadata": {"plan": "pro"}}
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert api.last.headers["idempotency-key"] == "k"

    api.add(200, VERIFICATION_VERIFIED)
    assert call(rayacash.IdentityVerification, "retrieve", VERIFICATION_ID).status == "verified"
    assert api.last.url.path == VERIFICATION_PATH

    api.add(200, VERIFICATION_LIST)
    page = call(rayacash.IdentityVerification, "list", status="verified", limit=2)
    assert type(page) is rayacash.ListObject
    assert type(page.data[0]) is rayacash.IdentityVerification
    assert dict(api.last.url.params) == {"status": "verified", "limit": "2"}

    api.add(200, VERIFICATION_CANCELED)
    canceled = call(rayacash.IdentityVerification, "cancel", VERIFICATION_ID, idempotency_key="c-1")
    assert canceled.status == "canceled"
    assert api.last.url.path == f"{VERIFICATION_PATH}/cancel"
    assert api.last.headers["idempotency-key"] == "c-1"

    api.add(200, VERIFICATION_FILES)
    files = call(rayacash.IdentityVerification, "files", VERIFICATION_ID)
    assert type(files) is rayacash.IdentityVerificationFiles
    assert api.last.url.path == f"{VERIFICATION_PATH}/files"


def test_identity_verification_cancel_by_id_without_a_key(
    global_api: MockAPI, call: Caller
) -> None:
    global_api.add(200, VERIFICATION_CANCELED)
    call(rayacash.IdentityVerification, "cancel", VERIFICATION_ID)
    assert global_api.last.content == b""
    assert uuid.UUID(global_api.last.headers["idempotency-key"]).version == 4


def test_identity_verification_instance_cancel(global_api: MockAPI, call: Caller) -> None:
    global_api.add(200, VERIFICATION_PENDING)
    verification = rayacash.IdentityVerification.retrieve(VERIFICATION_ID)
    global_api.add(200, VERIFICATION_CANCELED)
    canceled = call(verification, "cancel")
    assert type(canceled) is rayacash.IdentityVerification
    assert canceled.status == "canceled"
    assert verification.status == "pending"  # devuelve una verificación nueva, no muta la original
    assert global_api.last.url.path == f"{VERIFICATION_PATH}/cancel"
    assert global_api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert uuid.UUID(global_api.last.headers["idempotency-key"]).version == 4


def test_identity_verification_instance_cancel_uses_the_client_it_came_from(
    global_api: MockAPI, call: Caller
) -> None:
    other_api = MockAPI()
    client = other_api.client(OTHER_KEY)
    other_api.add(200, VERIFICATION_PENDING)
    verification = client.identity.verifications.retrieve(VERIFICATION_ID)
    other_api.add(200, VERIFICATION_CANCELED)
    call(verification, "cancel", idempotency_key="c-3")
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert other_api.last.headers["idempotency-key"] == "c-3"
    # También las de una página: cada verificación recuerda el cliente del que vino.
    other_api.add(200, VERIFICATION_LIST)
    page = client.identity.verifications.list()
    other_api.add(200, VERIFICATION_CANCELED)
    call(page.data[1], "cancel")
    assert other_api.last.url.path == f"{VERIFICATION_PATH}/cancel"
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert global_api.requests == []


def test_identity_events_from_construct_event_use_the_global_style(global_api: MockAPI) -> None:
    # Un identity.verification.verified firmado, de punta a punta: person viene en None.
    body = json.dumps(EVENT_VERIFICATION_VERIFIED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert event.type == "identity.verification.verified"
    verification = event.data.object
    assert isinstance(verification, rayacash.IdentityVerification)
    assert verification.person is None
    global_api.add(200, VERIFICATION_CANCELED)
    asyncio.run(verification.cancel_async(idempotency_key="c-2"))
    assert global_api.last.url.path == f"{VERIFICATION_PATH}/cancel"
    assert global_api.last.headers["idempotency-key"] == "c-2"


def test_identity_events_from_client_construct_event_use_that_client(
    global_api: MockAPI,
) -> None:
    other_api = MockAPI()
    client = other_api.client(OTHER_KEY)
    body = json.dumps(EVENT_VERIFICATION_VERIFIED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    verification = client.construct_event(body, header, WEBHOOK_SECRET).data.object
    assert isinstance(verification, rayacash.IdentityVerification)
    other_api.add(200, VERIFICATION_CANCELED)
    verification.cancel()
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert global_api.requests == []


def test_identity_verification_cancel_needs_an_id(call: Caller) -> None:
    verification = rayacash.IdentityVerification.construct_from({"object": "identity.verification"})
    with pytest.raises(
        ValueError, match=r"^Esta IdentityVerification no tiene id: no se puede cancelar\.$"
    ):
        call(verification, "cancel")


def test_identity_verification_without_any_key(api: MockAPI, call: Caller) -> None:
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    with pytest.raises(rayacash.AuthenticationError) as info:
        call(rayacash.IdentityVerification, "retrieve", VERIFICATION_ID)
    assert info.value.code == "API_KEY_MISSING"
    assert api.requests == []


# --- Sandbox: rayacash.Payment.simulate_transfer, con la clave secreta de prueba ---------------


def test_sandbox_simulate_transfer(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    rayacash.api_key = SANDBOX_KEY  # la clave secreta de prueba del sandbox
    api.add(200, SANDBOX_PAYMENT_FAILED)
    payment = call(rayacash.Payment, "simulate_transfer", SANDBOX_PAYMENT_ID, amount=1000)
    assert type(payment) is rayacash.Payment
    assert payment.failure_code == "amount_mismatch"
    request = api.last
    assert (request.method, request.url.path) == (
        "POST",
        f"/v1/test/payments/{SANDBOX_PAYMENT_ID}/simulate_transfer",
    )
    assert request.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    assert "idempotency-key" not in request.headers
    assert json.loads(request.content) == {"amount": 1000}

    # Con el id de una orden de Raya Connect de una app del sandbox, vuelve el ConnectOrder.
    api.add(200, SANDBOX_ORDER_SUCCEEDED)
    order = call(rayacash.Payment, "simulate_transfer", SANDBOX_ORDER_ID)
    assert type(order) is rayacash.ConnectOrder
    assert api.last.url.path == f"/v1/test/payments/{SANDBOX_ORDER_ID}/simulate_transfer"
    assert api.last.content == b""
    assert "idempotency-key" not in api.last.headers


def test_sandbox_simulate_transfer_without_any_key(api: MockAPI, call: Caller) -> None:
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    with pytest.raises(rayacash.AuthenticationError) as info:
        call(rayacash.Payment, "simulate_transfer", SANDBOX_PAYMENT_ID)
    assert info.value.code == "API_KEY_MISSING"
    assert api.requests == []


# --- Raya PSP: rayacash.PspCustomer, PspTransfer y PspBalance, con la clave secreta ------------

PSP_CUSTOMER_PATH = f"/v1/psp/customers/{psp.CUSTOMER_ID}"
PSP_CUSTOMER_ACTIONS = ["block", "unblock", "close", "recreate"]


def test_psp_endpoints(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    api.add(201, psp.CUSTOMER_ACTIVE)
    customer = call(
        rayacash.PspCustomer,
        "create",
        metadata={"plan": "pro"},
        identity_verification=VERIFICATION_ID,
        idempotency_key="alta-1",
    )
    assert type(customer) is rayacash.PspCustomer
    assert api.last.url.path == "/v1/psp/customers"
    assert json.loads(api.last.content) == {
        "identity_verification": VERIFICATION_ID,
        "metadata": {"plan": "pro"},
    }
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert api.last.headers["idempotency-key"] == "alta-1"

    api.add(200, psp.CUSTOMER_WITH_BALANCE)
    assert call(rayacash.PspCustomer, "retrieve", psp.CUSTOMER_ID).balance == 23649.5
    assert api.last.url.path == PSP_CUSTOMER_PATH

    api.add(200, psp.CUSTOMER_LIST)
    page = call(rayacash.PspCustomer, "list", status="active", limit=2)
    assert type(page) is rayacash.ListObject
    assert type(page.data[0]) is rayacash.PspCustomer
    assert dict(api.last.url.params) == {"status": "active", "limit": "2"}

    api.add(200, psp.CUSTOMER_BALANCE)
    balance = call(rayacash.PspCustomer, "retrieve_balance", psp.CUSTOMER_ID)
    assert type(balance) is rayacash.PspCustomerBalance
    assert api.last.url.path == f"{PSP_CUSTOMER_PATH}/balance"

    for action in PSP_CUSTOMER_ACTIONS:
        api.add(200, psp.CUSTOMER_ACTIVE)
        result = call(rayacash.PspCustomer, action, psp.CUSTOMER_ID, idempotency_key=f"{action}-1")
        assert type(result) is rayacash.PspCustomer
        assert api.last.url.path == f"{PSP_CUSTOMER_PATH}/{action}"
        assert api.last.content == b""
        assert api.last.headers["idempotency-key"] == f"{action}-1"

    api.add(201, psp.TRANSFER_OUTBOUND_PENDING)
    transfer = call(
        rayacash.PspTransfer,
        "create",
        customer=psp.CUSTOMER_ID,
        amount=18350.5,
        destination=psp.SUPPLIER_ACCOUNT,
        idempotency_key="t-1",
    )
    assert type(transfer) is rayacash.PspTransfer
    assert api.last.url.path == "/v1/psp/transfers"
    assert api.last.headers["idempotency-key"] == "t-1"

    api.add(200, psp.TRANSFER_INBOUND)
    assert call(rayacash.PspTransfer, "retrieve", psp.INBOUND_ID).direction == "inbound"
    assert api.last.url.path == f"/v1/psp/transfers/{psp.INBOUND_ID}"

    api.add(200, psp.TRANSFER_LIST)
    transfers = call(rayacash.PspTransfer, "list", customer=psp.CUSTOMER_ID, limit=2)
    assert [type(item) for item in transfers] == [rayacash.PspTransfer] * 2
    assert dict(api.last.url.params) == {"customer": psp.CUSTOMER_ID, "limit": "2"}

    api.add(200, psp.PSP_BALANCE)
    assert type(call(rayacash.PspBalance, "retrieve")) is rayacash.PspBalance
    assert api.last.url.path == "/v1/psp/balance"


def test_psp_customer_create_in_the_global_style_takes_the_three_forms(
    global_api: MockAPI, call: Caller
) -> None:
    # PspCustomer.create reenvía todo, también los None, al mismo body que client.psp.customers:
    # con Identidad, con las fotos o una persona jurídica, en el orden de la API.
    company = {
        "tax_id": psp.COMPANY_TAX_ID,
        "name": psp.COMPANY_NAME,
        "person_type": "J",
        "external_reference": "cliente-8813",
    }
    for body in (psp.CREATE_BODY, psp.PHOTOS_BODY, company):
        global_api.add(202, psp.CUSTOMER_VERIFYING)
        call(rayacash.PspCustomer, "create", **dict(reversed(body.items())))
        assert global_api.last.url.path == "/v1/psp/customers"
        assert list(json.loads(global_api.last.content).items()) == list(body.items())
    # Sin identity_verification, tax_id y name son obligatorios: el mismo TypeError, sin mandar.
    with pytest.raises(TypeError, match=r"^tax_id tiene que ser un str: .* mandá solo identity_"):
        call(rayacash.PspCustomer, "create", person_type="J")
    with pytest.raises(TypeError, match=r"^identity_verification .*\(idv_…\), no int\.$"):
        call(rayacash.PspCustomer, "create", identity_verification=1234)
    assert len(global_api.requests) == 3


def test_psp_transfer_create_requires_an_idempotency_key_in_the_global_style(
    global_api: MockAPI,
) -> None:
    transfer: Any = rayacash.PspTransfer  # llamadas que el type checker ya rechaza
    with pytest.raises(TypeError, match="idempotency_key"):
        transfer.create(customer=psp.CUSTOMER_ID, amount=1, destination="x")
    with pytest.raises(TypeError, match=r"^psp\.transfers\.create necesita idempotency_key"):
        transfer.create(customer=psp.CUSTOMER_ID, amount=1, destination="x", idempotency_key=None)
    assert global_api.requests == []


def test_psp_customer_actions_by_id_without_a_key(global_api: MockAPI, call: Caller) -> None:
    for action in PSP_CUSTOMER_ACTIONS:
        global_api.add(200, psp.CUSTOMER_ACTIVE)
        call(rayacash.PspCustomer, action, psp.CUSTOMER_ID)
        assert global_api.last.content == b""
        assert uuid.UUID(global_api.last.headers["idempotency-key"]).version == 4


@pytest.mark.parametrize("action", PSP_CUSTOMER_ACTIONS)
def test_psp_customer_instance_actions(global_api: MockAPI, call: Caller, action: str) -> None:
    global_api.add(200, psp.CUSTOMER_ACTIVE)
    customer = rayacash.PspCustomer.retrieve(psp.CUSTOMER_ID)
    global_api.add(200, psp.CUSTOMER_BLOCKED)
    result = call(customer, action)
    assert type(result) is rayacash.PspCustomer
    assert result.status == "blocked"
    assert customer.status == "active"  # devuelve un cliente nuevo, no muta el original
    assert global_api.last.method == "POST"
    assert global_api.last.url.path == f"{PSP_CUSTOMER_PATH}/{action}"
    assert global_api.last.content == b""
    assert global_api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert uuid.UUID(global_api.last.headers["idempotency-key"]).version == 4


def test_psp_customer_instance_actions_use_the_client_it_came_from(
    global_api: MockAPI, call: Caller
) -> None:
    other_api = MockAPI()
    client = other_api.client(OTHER_KEY)
    other_api.add(200, psp.CUSTOMER_ACTIVE)
    customer = client.psp.customers.retrieve(psp.CUSTOMER_ID)
    other_api.add(200, psp.CUSTOMER_BLOCKED)
    call(customer, "block", idempotency_key="b-1")
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert other_api.last.headers["idempotency-key"] == "b-1"
    # También los de una página: cada cliente recuerda el RayaClient del que vino.
    other_api.add(200, psp.CUSTOMER_LIST)
    page = client.psp.customers.list()
    other_api.add(200, psp.CUSTOMER_ACTIVE)
    call(page.data[0], "recreate")
    assert other_api.last.url.path == f"/v1/psp/customers/{psp.COMPANY_ID}/recreate"
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert global_api.requests == []


def test_psp_events_from_construct_event_use_the_global_style(global_api: MockAPI) -> None:
    # Un psp.customer.activated firmado, de punta a punta.
    body = json.dumps(psp.EVENT_CUSTOMER_ACTIVATED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert event.type == "psp.customer.activated"
    customer = event.data.object
    assert isinstance(customer, rayacash.PspCustomer)
    assert customer.cvu is not None
    assert customer.cvu.alias == "maria_ejemplo"
    global_api.add(200, psp.CUSTOMER_BLOCKED)
    asyncio.run(customer.block_async(idempotency_key="b-2"))
    assert global_api.last.url.path == f"{PSP_CUSTOMER_PATH}/block"
    assert global_api.last.headers["idempotency-key"] == "b-2"


def test_psp_events_from_client_construct_event_use_that_client(global_api: MockAPI) -> None:
    other_api = MockAPI()
    client = other_api.client(OTHER_KEY)
    body = json.dumps(psp.EVENT_CUSTOMER_ACTIVATED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    customer = client.construct_event(body, header, WEBHOOK_SECRET).data.object
    assert isinstance(customer, rayacash.PspCustomer)
    other_api.add(200, psp.CUSTOMER_CLOSED)
    assert customer.close().status == "closed"
    assert other_api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"
    assert global_api.requests == []


@pytest.mark.parametrize(
    ("action", "verb"),
    [
        ("block", "bloquear"),
        ("unblock", "desbloquear"),
        ("close", "dar de baja su CVU"),
        ("recreate", "recrear su CVU"),
    ],
)
def test_psp_customer_actions_need_an_id(call: Caller, action: str, verb: str) -> None:
    customer = rayacash.PspCustomer.construct_from({"object": "psp.customer"})
    with pytest.raises(ValueError, match=rf"^Este PspCustomer no tiene id: no se puede {verb}\.$"):
        call(customer, action)


def test_psp_without_any_key(api: MockAPI, call: Caller) -> None:
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    for owner, method, args in (
        (rayacash.PspCustomer, "retrieve", (psp.CUSTOMER_ID,)),
        (rayacash.PspCustomer, "block", (psp.CUSTOMER_ID,)),
        (rayacash.PspTransfer, "retrieve", (psp.OUTBOUND_ID,)),
        (rayacash.PspBalance, "retrieve", ()),
    ):
        with pytest.raises(rayacash.AuthenticationError) as info:
            call(owner, method, *args)
        assert info.value.code == "API_KEY_MISSING"
    assert api.requests == []


# --- Facturador: rayacash.Invoice, con la clave secreta -------------------------------------------


def test_invoice_endpoints(global_api: MockAPI, call: Caller) -> None:
    api = global_api
    api.add(202, facturador.INVOICE_PENDING)
    invoice = call(
        rayacash.Invoice,
        "create",
        metadata={"pedido": "1042"},
        amount=15000,
        dni=facturador.DNI,
        idempotency_key="venta-1042",
    )
    assert type(invoice) is rayacash.Invoice
    assert invoice.status == "pending"
    assert api.last.method == "POST"
    assert api.last.url.path == "/v1/invoices"
    assert list(json.loads(api.last.content).items()) == list(facturador.CREATE_BODY.items())
    assert api.last.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert api.last.headers["idempotency-key"] == "venta-1042"

    api.add(200, facturador.INVOICE_ISSUED)
    issued = call(rayacash.Invoice, "retrieve", facturador.INVOICE_ID)
    assert (issued.status, issued.cae) == ("issued", facturador.CAE)
    assert api.last.url.path == f"/v1/invoices/{facturador.INVOICE_ID}"

    api.add(200, facturador.INVOICE_LIST)
    page = call(rayacash.Invoice, "list", status="issued", limit=2)
    assert type(page) is rayacash.ListObject
    assert [type(item) for item in page] == [rayacash.Invoice] * 2
    assert dict(api.last.url.params) == {"status": "issued", "limit": "2"}


def test_invoice_create_requires_an_idempotency_key_in_the_global_style(
    global_api: MockAPI, call: Caller
) -> None:
    invoice: Any = rayacash.Invoice  # llamadas que el type checker ya rechaza
    with pytest.raises(TypeError, match="idempotency_key"):
        call(invoice, "create", dni=facturador.DNI, amount=15000)
    with pytest.raises(TypeError, match=r"^invoices\.create necesita idempotency_key"):
        call(invoice, "create", dni=facturador.DNI, amount=15000, idempotency_key=None)
    with pytest.raises(TypeError, match=r"^dni tiene que ser un DNI de 6 a 8 dígitos, como texto"):
        call(invoice, "create", dni=12345678, amount=15000, idempotency_key="k")
    assert global_api.requests == []


def test_invoice_events_from_construct_event(global_api: MockAPI) -> None:
    # Un invoice.issued firmado, de punta a punta: la factura llega con su número y su CAE.
    body = json.dumps(facturador.EVENT_INVOICE_ISSUED)
    header = rayacash.WebhookSignature.generate_header(body, WEBHOOK_SECRET)
    event = rayacash.Webhook.construct_event(body, header, WEBHOOK_SECRET)
    assert event.type == "invoice.issued"
    invoice = event.data.object
    assert isinstance(invoice, rayacash.Invoice)
    assert (invoice.number, invoice.cae) == (1234, facturador.CAE)
    # Para el estado de ahora, retrieve con la configuración global.
    global_api.add(200, facturador.INVOICE_ISSUED)
    assert rayacash.Invoice.retrieve(invoice.id).status == "issued"
    assert global_api.last.headers["authorization"] == f"Bearer {TEST_KEY}"


def test_invoice_with_a_key_per_call(api: MockAPI, call: Caller) -> None:
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    api.add(200, facturador.INVOICE_ISSUED)
    call(rayacash.Invoice, "retrieve", facturador.INVOICE_ID, options={"api_key": OTHER_KEY})
    assert api.last.headers["authorization"] == f"Bearer {OTHER_KEY}"


def test_invoice_without_any_key(api: MockAPI, call: Caller) -> None:
    rayacash.http_client = api.sync_client()
    rayacash.async_http_client = api.async_client()
    for method, args, kwargs in (
        ("create", (), {"dni": facturador.DNI, "amount": 15000, "idempotency_key": "k"}),
        ("retrieve", (facturador.INVOICE_ID,), {}),
        ("list", (), {}),
    ):
        with pytest.raises(rayacash.AuthenticationError) as info:
            call(rayacash.Invoice, method, *args, **kwargs)
        assert info.value.code == "API_KEY_MISSING"
    assert api.requests == []
