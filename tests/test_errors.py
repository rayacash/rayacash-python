from __future__ import annotations

import json
import pickle
from typing import Any, NoReturn

import httpx
import pytest

import rayacash
from rayacash._error import error_from_response

# Los 51 códigos del contrato (api.md › Códigos de error): los 32 de siempre, los 11 de Raya
# Connect (apps y cuentas conectadas), los 2 de los payouts, los 4 de Identidad (con
# SANDBOX_NOT_SUPPORTED, el 403 de una credencial de prueba en un endpoint que todavía no está
# disponible en el sandbox, e IDENTITY_NOT_ACTIVATED, al final de los 403) y los 2 del helper del
# sandbox (SANDBOX_ONLY, después de SANDBOX_NOT_SUPPORTED, y PAYMENT_NOT_PENDING, después de
# PAYMENT_NOT_REFUNDABLE). El test no mira el orden.
CATALOG: list[tuple[str, int, type[rayacash.RayaError]]] = [
    ("INVALID_JSON", 400, rayacash.InvalidRequestError),
    ("PARAMETER_MISSING", 400, rayacash.InvalidRequestError),
    ("PARAMETER_INVALID", 400, rayacash.InvalidRequestError),
    ("PARAMETER_UNKNOWN", 400, rayacash.InvalidRequestError),
    ("OAUTH_GRANT_INVALID", 400, rayacash.InvalidRequestError),
    ("OAUTH_GRANT_TYPE_UNSUPPORTED", 400, rayacash.InvalidRequestError),
    ("API_KEY_MISSING", 401, rayacash.AuthenticationError),
    ("API_KEY_INVALID", 401, rayacash.AuthenticationError),
    ("API_KEY_PUBLISHABLE_NOT_ALLOWED", 401, rayacash.AuthenticationError),
    ("API_KEY_EXPIRED", 401, rayacash.AuthenticationError),
    ("ACCESS_TOKEN_MISSING", 401, rayacash.AuthenticationError),
    ("ACCESS_TOKEN_INVALID", 401, rayacash.AuthenticationError),
    ("ACCESS_TOKEN_REVOKED", 401, rayacash.AuthenticationError),
    ("OAUTH_CLIENT_INVALID", 401, rayacash.AuthenticationError),
    ("API_KEY_ACCOUNT_LOCKED", 403, rayacash.PermissionDeniedError),
    ("API_NOT_ENABLED", 403, rayacash.PermissionDeniedError),
    ("MERCHANT_NOT_CONFIGURED", 403, rayacash.PermissionDeniedError),
    ("TRANSFERS_BLOCKED", 403, rayacash.PermissionDeniedError),
    ("CONNECTED_ACCOUNT_LOCKED", 403, rayacash.PermissionDeniedError),
    ("CONNECTED_ACCOUNT_NOT_CONFIGURED", 403, rayacash.PermissionDeniedError),
    ("APP_DISABLED", 403, rayacash.PermissionDeniedError),
    ("PAYOUT_ORIGIN_UNAVAILABLE", 403, rayacash.PermissionDeniedError),
    ("SANDBOX_NOT_SUPPORTED", 403, rayacash.PermissionDeniedError),
    ("SANDBOX_ONLY", 403, rayacash.PermissionDeniedError),
    ("IDENTITY_NOT_ACTIVATED", 403, rayacash.PermissionDeniedError),
    ("TRANSFER_NOT_FOUND", 404, rayacash.NotFoundError),
    ("PAYMENT_NOT_FOUND", 404, rayacash.NotFoundError),
    ("NOT_FOUND", 404, rayacash.NotFoundError),
    ("USER_NOT_FOUND", 404, rayacash.NotFoundError),
    ("ORDER_NOT_FOUND", 404, rayacash.NotFoundError),
    ("PAYOUT_NOT_FOUND", 404, rayacash.NotFoundError),
    ("VERIFICATION_NOT_FOUND", 404, rayacash.NotFoundError),
    ("METHOD_NOT_ALLOWED", 405, rayacash.InvalidRequestError),
    ("IDEMPOTENCY_KEY_REUSED", 409, rayacash.IdempotencyError),
    ("IDEMPOTENCY_KEY_IN_USE", 409, rayacash.IdempotencyError),
    ("PAYMENT_NOT_REFUNDABLE", 409, rayacash.ConflictError),
    ("PAYMENT_NOT_PENDING", 409, rayacash.ConflictError),
    ("VERIFICATION_NOT_CANCELABLE", 409, rayacash.ConflictError),
    ("REQUEST_TOO_LARGE", 413, rayacash.InvalidRequestError),
    ("INSUFFICIENT_BALANCE", 422, rayacash.UnprocessableEntityError),
    ("LIMIT_EXCEEDED", 422, rayacash.UnprocessableEntityError),
    ("DESTINATION_NOT_FOUND", 422, rayacash.UnprocessableEntityError),
    ("DESTINATION_INACTIVE", 422, rayacash.UnprocessableEntityError),
    ("DESTINATION_NOT_SUPPORTED", 422, rayacash.UnprocessableEntityError),
    ("REFUND_FAILED", 422, rayacash.UnprocessableEntityError),
    ("RATE_LIMITED", 429, rayacash.RateLimitError),
    ("INTERNAL_ERROR", 500, rayacash.APIError),
    ("BANK_UNAVAILABLE", 503, rayacash.APIError),
    ("CVU_UNAVAILABLE", 503, rayacash.APIError),
    ("API_UNAVAILABLE", 503, rayacash.APIError),
    ("TEMPORARILY_UNAVAILABLE", 503, rayacash.APIError),
]


def make_error(
    status: int,
    body: Any,
    headers: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> rayacash.RayaError:
    text = body if isinstance(body, str) else json.dumps(body)
    return error_from_response(
        http_status=status,
        headers=httpx.Headers({"Raya-Request-Id": "req_abc", **(headers or {})}),
        body=text,
        idempotency_key=idempotency_key,
    )


def test_catalog_has_the_51_codes() -> None:
    assert len({code for code, _, _ in CATALOG}) == 51
    assert len(CATALOG) == 51


@pytest.mark.parametrize(("code", "status", "cls"), CATALOG)
def test_every_code_maps_to_its_class(
    code: str, status: int, cls: type[rayacash.RayaError]
) -> None:
    error = make_error(status, {"error": {"code": code, "message": "Texto.", "data": None}})
    assert type(error) is cls
    assert isinstance(error, rayacash.RayaError)
    assert error.code == code
    assert error.http_status == status
    assert error.message == "Texto."
    assert error.request_id == "req_abc"


def test_error_attributes() -> None:
    body = {
        "error": {
            "code": "PARAMETER_INVALID",
            "message": "amount tiene que ser un número con hasta 2 decimales.",
            "data": {"field": "amount"},
        }
    }
    error = make_error(400, body, {"Retry-After": "3"}, idempotency_key="key-1")
    assert isinstance(error, rayacash.InvalidRequestError)
    assert error.param == "amount"
    assert error.data == {"field": "amount"}
    assert error.json_body == body
    assert error.http_body == json.dumps(body)
    assert error.headers["raya-request-id"] == "req_abc"
    assert error.idempotency_key == "key-1"
    assert error.retry_after == 3.0
    assert error.user_message == error.message
    assert str(error) == (
        "Request req_abc: amount tiene que ser un número con hasta 2 decimales. (PARAMETER_INVALID)"
    )
    assert repr(error) == (
        "InvalidRequestError(message='amount tiene que ser un número con hasta 2 decimales.', "
        "http_status=400, code='PARAMETER_INVALID', request_id='req_abc')"
    )


def test_connected_account_locked_carries_the_reason() -> None:
    # El único de los códigos de apps con data: {"reason": "kyc_required" | "user_blocked"}.
    error = make_error(
        403,
        {
            "error": {
                "code": "CONNECTED_ACCOUNT_LOCKED",
                "message": "La cuenta conectada no puede operar en este momento.",
                "data": {"reason": "kyc_required"},
            }
        },
    )
    assert type(error) is rayacash.PermissionDeniedError
    assert error.data == {"reason": "kyc_required"}
    revoked = make_error(
        401, {"error": {"code": "ACCESS_TOKEN_REVOKED", "message": "x", "data": None}}
    )
    assert type(revoked) is rayacash.AuthenticationError
    assert revoked.data is None


def test_param_is_none_without_field() -> None:
    error = make_error(400, {"error": {"code": "INVALID_JSON", "message": "x", "data": None}})
    assert isinstance(error, rayacash.InvalidRequestError)
    assert error.param is None


def test_payment_not_refundable_with_and_without_reason() -> None:
    with_reason = make_error(
        409,
        {
            "error": {
                "code": "PAYMENT_NOT_REFUNDABLE",
                "message": "x",
                "data": {"status": "succeeded", "reason": "refund_window_expired"},
            }
        },
    )
    assert with_reason.data == {"status": "succeeded", "reason": "refund_window_expired"}
    without = make_error(
        409,
        {
            "error": {
                "code": "PAYMENT_NOT_REFUNDABLE",
                "message": "x",
                "data": {"status": "refunded"},
            }
        },
    )
    assert type(without) is rayacash.ConflictError
    assert without.data == {"status": "refunded"}


def test_verification_not_cancelable_carries_the_status() -> None:
    error = make_error(
        409,
        {
            "error": {
                "code": "VERIFICATION_NOT_CANCELABLE",
                "message": "Solo podés cancelar verificaciones pending o in_progress.",
                "data": {"status": "processing"},
            }
        },
    )
    assert type(error) is rayacash.ConflictError  # no es un IdempotencyError
    assert error.data == {"status": "processing"}


def test_the_sandbox_codes_keep_their_message_and_data() -> None:
    # Los dos del helper del sandbox, con los mensajes literales de la API.
    not_pending = make_error(
        409,
        {
            "error": {
                "code": "PAYMENT_NOT_PENDING",
                "message": "Solo podés simular la transferencia de un pago pendiente.",
                "data": {"status": "expired"},
            }
        },
    )
    assert type(not_pending) is rayacash.ConflictError  # no es un IdempotencyError
    assert not_pending.data == {"status": "expired"}
    message = "Este endpoint solo funciona en un sandbox: usá una credencial de prueba."
    only = make_error(403, {"error": {"code": "SANDBOX_ONLY", "message": message, "data": None}})
    assert type(only) is rayacash.PermissionDeniedError
    assert only.message == message
    assert only.data is None


def test_the_verification_limit_comes_as_rate_limited() -> None:
    # Los topes de Identidad (verificaciones abiertas o por día): data.limit y Retry-After: 3600.
    error = make_error(
        429,
        {"error": {"code": "RATE_LIMITED", "message": "x", "data": {"limit": "daily"}}},
        {"Retry-After": "3600"},
    )
    assert type(error) is rayacash.RateLimitError
    assert error.retry_after == 3600.0
    assert error.data == {"limit": "daily"}


@pytest.mark.parametrize(
    ("status", "code", "cls"),
    [
        (422, "NEW_BUSINESS_RULE", rayacash.UnprocessableEntityError),
        (409, "NEW_CONFLICT", rayacash.ConflictError),
        (409, "IDEMPOTENCY_KEY_NEW", rayacash.IdempotencyError),
        (418, "TEAPOT", rayacash.InvalidRequestError),
        (410, "GONE", rayacash.InvalidRequestError),
        (599, "WEIRD", rayacash.APIError),
        (302, "MOVED", rayacash.APIError),
    ],
)
def test_unknown_codes_follow_the_http_status(
    status: int, code: str, cls: type[rayacash.RayaError]
) -> None:
    error = make_error(status, {"error": {"code": code, "message": "x", "data": None}})
    assert type(error) is cls
    assert error.code == code


@pytest.mark.parametrize(
    ("status", "body", "cls", "code"),
    [
        (502, "<html>Bad gateway</html>", rayacash.APIError, "INTERNAL_ERROR"),
        (504, "", rayacash.APIError, "INTERNAL_ERROR"),
        (408, "timeout", rayacash.APIError, "INTERNAL_ERROR"),
        (429, "<html>Cloudflare</html>", rayacash.RateLimitError, "RATE_LIMITED"),
        (404, "<h1>Not Found</h1>", rayacash.NotFoundError, "INVALID_RESPONSE"),
        (403, {"detail": "CSRF"}, rayacash.PermissionDeniedError, "INVALID_RESPONSE"),
        (400, {"error": "texto"}, rayacash.InvalidRequestError, "INVALID_RESPONSE"),
        (500, ["no", "es", "un", "objeto"], rayacash.APIError, "INTERNAL_ERROR"),
    ],
)
def test_responses_without_the_error_object(
    status: int, body: Any, cls: type[rayacash.RayaError], code: str
) -> None:
    error = make_error(status, body)
    assert type(error) is cls
    assert error.code == code
    assert error.message  # siempre hay un mensaje en castellano
    assert error.data is None


@pytest.mark.parametrize(
    ("status", "cls", "code"),
    [
        (500, rayacash.APIError, "INTERNAL_ERROR"),
        (429, rayacash.RateLimitError, "RATE_LIMITED"),
        (400, rayacash.InvalidRequestError, "INVALID_RESPONSE"),
    ],
)
def test_error_bodies_too_deep_to_read(
    status: int,
    cls: type[rayacash.RayaError],
    code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Como cualquier body que no se puede leer (antes salía un RecursionError). El RecursionError
    # es simulado: cuántos niveles lee json depende de la versión y de la plataforma.
    def too_deep(*args: object, **kwargs: object) -> NoReturn:
        raise RecursionError("maximum recursion depth exceeded while decoding a JSON array")

    monkeypatch.setattr(json, "loads", too_deep)
    body = '{"error":{"code":"X","data":[[[]]]}}'
    error = make_error(status, body)
    assert type(error) is cls
    assert error.code == code
    assert error.json_body is None
    assert error.http_body == body
    assert error.request_id == "req_abc"


def test_a_deep_error_body_never_raises_recursion_error() -> None:
    # Desde 3.14, json mide la pila real, así que leer 100 000 niveles depende de la plataforma (en
    # el runner de GitHub los lee). Lo que lee conserva su código, como en Node; lo que no, lleva
    # el de respaldo.
    body = '{"error":{"code":"X","data":' + "[" * 100_000 + "]" * 100_000 + "}}"
    try:
        json.loads(body)
        expected = "X"
    except RecursionError:
        expected = "INTERNAL_ERROR"
    error = make_error(500, body)
    assert type(error) is rayacash.APIError
    assert error.code == expected
    assert error.http_body == body


def test_message_falls_back_when_code_is_missing() -> None:
    error = make_error(500, {"error": {"message": "Algo falló.", "data": {"x": 1}}})
    assert error.code == "INTERNAL_ERROR"
    assert error.message == "Algo falló."
    assert error.data == {"x": 1}


def test_str_without_request_id_or_code() -> None:
    assert str(rayacash.RayaError("Hola")) == "Hola"
    assert str(rayacash.RayaError()) == "<sin mensaje>"
    assert str(rayacash.RayaError("Hola", code="X")) == "Hola (X)"


def test_connection_and_signature_errors() -> None:
    error = rayacash.APIConnectionError("Sin red.", code="NETWORK_ERROR", should_retry=True)
    assert error.should_retry is True
    assert error.http_status is None
    signature = rayacash.SignatureVerificationError("Mala firma.", "t=1,v1=x", "{}")
    assert signature.sig_header == "t=1,v1=x"
    assert signature.http_body == "{}"
    assert signature.code is None


def test_errors_survive_pickle() -> None:
    error = pickle.loads(pickle.dumps(rayacash.APIError("Falló.")))
    assert isinstance(error, rayacash.APIError)
    assert error.message == "Falló."
