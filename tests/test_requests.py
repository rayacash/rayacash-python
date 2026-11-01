"""Reintentos, idempotencia y logging del núcleo de requests."""

from __future__ import annotations

import logging

import httpx
import pytest

import rayacash
from tests.fixtures import (
    BALANCE,
    PAYMENT_ID,
    PAYMENT_PENDING,
    PAYMENT_REFUNDED,
    TRANSFER_OUTBOUND_PENDING,
)
from tests.helpers import TEST_KEY, Caller, MockAPI


def create_payment(client: rayacash.RayaClient, call: Caller, **kwargs: object) -> rayacash.Payment:
    result = call(client.payments, "create", amount=15000, **kwargs)
    assert isinstance(result, rayacash.Payment)
    return result


def test_retries_reuse_the_same_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    api.add_error(503, "TEMPORARILY_UNAVAILABLE", headers={"Retry-After": "5"})
    api.add_error(500, "INTERNAL_ERROR")
    api.add(201, PAYMENT_PENDING)
    payment = create_payment(client, call)
    keys = {request.headers["idempotency-key"] for request in api.requests}
    assert len(api.requests) == 3
    assert len(keys) == 1
    assert payment.last_response is not None
    assert payment.last_response.idempotency_key == keys.pop()
    assert sleeps == [5.0, 1.0]  # Retry-After y después el backoff (jitter fijo en el máximo)


def test_gives_up_after_max_network_retries(
    client: rayacash.RayaClient, api: MockAPI, call: Caller, sleeps: list[float]
) -> None:
    for _ in range(3):
        api.add_error(500, "INTERNAL_ERROR")
    with pytest.raises(rayacash.APIError) as info:
        create_payment(client, call, idempotency_key="pedido-1")
    assert len(api.requests) == 3
    assert sleeps == [0.5, 1.0]
    assert info.value.code == "INTERNAL_ERROR"
    assert info.value.idempotency_key == "pedido-1"


@pytest.mark.parametrize(
    ("status", "code", "headers", "error"),
    [
        (409, "IDEMPOTENCY_KEY_REUSED", {}, rayacash.IdempotencyError),
        (409, "PAYMENT_NOT_REFUNDABLE", {}, rayacash.ConflictError),
        (503, "API_UNAVAILABLE", {}, rayacash.APIError),
        (429, "RATE_LIMITED", {"Retry-After": "120"}, rayacash.RateLimitError),
        (503, "BANK_UNAVAILABLE", {"Retry-After": "3600"}, rayacash.APIError),
        (400, "PARAMETER_INVALID", {}, rayacash.InvalidRequestError),
        (401, "API_KEY_EXPIRED", {}, rayacash.AuthenticationError),
        (403, "API_NOT_ENABLED", {}, rayacash.PermissionDeniedError),
        (422, "REFUND_FAILED", {}, rayacash.UnprocessableEntityError),
    ],
)
def test_not_retried(
    client: rayacash.RayaClient,
    api: MockAPI,
    sleeps: list[float],
    status: int,
    code: str,
    headers: dict[str, str],
    error: type[rayacash.RayaError],
) -> None:
    api.add_error(status, code, headers=headers)
    with pytest.raises(error) as info:
        client.payments.refund(PAYMENT_ID)
    assert len(api.requests) == 1
    assert sleeps == []
    if "Retry-After" in headers:
        assert info.value.retry_after == float(headers["Retry-After"])


@pytest.mark.parametrize(
    ("status", "code", "headers", "expected_sleep"),
    [
        (409, "IDEMPOTENCY_KEY_IN_USE", {"Retry-After": "2"}, 2.0),
        (429, "RATE_LIMITED", {"Retry-After": "7"}, 7.0),
        (429, "RATE_LIMITED", {}, 0.5),
        (503, "CVU_UNAVAILABLE", {"Retry-After": "5"}, 5.0),
        (503, "BANK_UNAVAILABLE", {}, 0.5),
        (503, "BANK_UNAVAILABLE", {"Retry-After": "30"}, 30.0),
    ],
)
def test_retried(
    client: rayacash.RayaClient,
    api: MockAPI,
    call: Caller,
    sleeps: list[float],
    status: int,
    code: str,
    headers: dict[str, str],
    expected_sleep: float,
) -> None:
    api.add_error(status, code, headers=headers)
    api.add(200, PAYMENT_REFUNDED)
    payment = call(client.payments, "refund", PAYMENT_ID)
    assert payment.status == "refunded"
    assert len(api.requests) == 2
    assert sleeps == [expected_sleep]


def test_edge_html_errors_are_retried(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(
        502, text="<html><body>Bad gateway</body></html>", headers={"Content-Type": "text/html"}
    )
    api.add(200, BALANCE)
    assert client.balance.retrieve().available == 152340.5
    assert len(api.requests) == 2


@pytest.mark.parametrize(
    ("exc", "code"),
    [(httpx.ConnectError("sin red"), "NETWORK_ERROR"), (httpx.ReadTimeout("lento"), "TIMEOUT")],
)
def test_connection_errors_are_retried(
    client: rayacash.RayaClient,
    api: MockAPI,
    call: Caller,
    sleeps: list[float],
    exc: Exception,
    code: str,
) -> None:
    api.fail_with(exc)
    api.add(201, TRANSFER_OUTBOUND_PENDING)
    transfer = call(
        client.transfers,
        "create",
        amount=25000,
        destination="proveedor.ejemplo",
        idempotency_key="k",
    )
    assert transfer.status == "pending"
    assert [r.headers["idempotency-key"] for r in api.requests] == ["k", "k"]
    assert sleeps == [0.5]


def test_connection_error_after_the_last_retry(
    client: rayacash.RayaClient, api: MockAPI, call: Caller
) -> None:
    for _ in range(3):
        api.fail_with(httpx.ReadTimeout("lento"))
    with pytest.raises(rayacash.APIConnectionError) as info:
        call(
            client.transfers,
            "create",
            amount=25000,
            destination="proveedor.ejemplo",
            idempotency_key="k",
        )
    error = info.value
    assert error.code == "TIMEOUT"
    assert error.should_retry is True
    assert error.idempotency_key == "k"
    assert "misma Idempotency-Key" in error.message
    assert isinstance(error.__cause__, httpx.ReadTimeout)


def test_get_connection_errors_have_no_idempotency_key(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    for _ in range(3):
        api.fail_with(httpx.ConnectError("sin red"))
    with pytest.raises(rayacash.APIConnectionError) as info:
        client.balance.retrieve()
    assert info.value.code == "NETWORK_ERROR"
    assert info.value.idempotency_key is None


def test_local_protocol_errors_are_not_retried(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.fail_with(httpx.LocalProtocolError("header inválido"))
    with pytest.raises(rayacash.APIConnectionError) as info:
        client.balance.retrieve()
    assert info.value.should_retry is False
    assert len(api.requests) == 1


def test_max_network_retries_per_client_and_per_request(api: MockAPI, sleeps: list[float]) -> None:
    client = api.client(max_network_retries=0)
    api.add_error(500, "INTERNAL_ERROR")
    with pytest.raises(rayacash.APIError):
        client.balance.retrieve()
    assert len(api.requests) == 1

    api.add_error(500, "INTERNAL_ERROR")
    api.add_error(500, "INTERNAL_ERROR")
    api.add(200, BALANCE)
    client.balance.retrieve(options={"max_network_retries": 4})
    assert len(api.requests) == 4

    default = api.client()
    api.add_error(500, "INTERNAL_ERROR")
    with pytest.raises(rayacash.APIError):
        default.balance.retrieve(options={"max_network_retries": 0})
    with pytest.raises(ValueError, match="max_network_retries"):
        default.balance.retrieve(options={"max_network_retries": -1})


@pytest.mark.parametrize("body", ["no es json", "[1, 2]", ""])
def test_success_without_a_json_object(
    client: rayacash.RayaClient, api: MockAPI, body: str
) -> None:
    api.add(200, text=body)
    with pytest.raises(rayacash.APIError) as info:
        client.balance.retrieve()
    assert info.value.code == "INVALID_RESPONSE"
    assert info.value.http_status == 200
    assert len(api.requests) == 1


def test_redirects_are_never_followed(client: rayacash.RayaClient, api: MockAPI) -> None:
    api.add(301, text="", headers={"Location": "https://otro.example/v1/balance"})
    with pytest.raises(rayacash.APIError) as info:
        client.balance.retrieve()
    assert info.value.http_status == 301
    assert len(api.requests) == 1


def test_list_endpoint_that_does_not_return_a_list(
    client: rayacash.RayaClient, api: MockAPI
) -> None:
    api.add(200, BALANCE)
    with pytest.raises(rayacash.APIError, match="no es una lista"):
        client.transfers.list()


def test_info_logs_never_include_the_key_or_the_body(
    client: rayacash.RayaClient,
    api: MockAPI,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    rayacash.log = "info"
    api.add_error(503, "TEMPORARILY_UNAVAILABLE", headers={"Retry-After": "5"})
    api.add(201, PAYMENT_PENDING)
    with caplog.at_level(logging.INFO, logger="rayacash"):
        client.payments.create(
            amount=15000, description="Pedido secreto", idempotency_key="clave-1"
        )
    err = capsys.readouterr().err
    assert 'message="Request a la API de Raya" method=POST path=/v1/payments attempt=1' in err
    assert "status=503" in err
    assert "Reintentando" in err
    assert "reason=TEMPORARILY_UNAVAILABLE" in err
    assert TEST_KEY not in err
    assert "Pedido secreto" not in err
    assert "clave-1" not in err  # la idempotency key solo sale en debug
    assert any("status=201" in record.getMessage() for record in caplog.records)


def test_debug_logs_include_the_idempotency_key(
    client: rayacash.RayaClient,
    api: MockAPI,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rayacash._util.RAYA_LOG", "debug")
    api.add(201, PAYMENT_PENDING)
    client.payments.create(amount=15000, idempotency_key="clave-1")
    err = capsys.readouterr().err
    assert "idempotency_key=clave-1" in err
    assert TEST_KEY not in err


def test_logging_is_quiet_by_default(
    client: rayacash.RayaClient, api: MockAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    api.add(200, BALANCE)
    client.balance.retrieve()
    assert capsys.readouterr().err == ""
