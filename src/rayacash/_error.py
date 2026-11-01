"""Errores del SDK.

La clase sale del código HTTP, como pide la API («si llega un código que no conocés, tratalo
según su código HTTP»). Para decidir qué hacer, usá ``error.code`` (estable), nunca
``error.message`` (texto para personas, puede cambiar).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from rayacash._retry import parse_retry_after


class RayaError(Exception):
    """Base de todos los errores del SDK."""

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        data: dict[str, Any] | None = None,
        http_status: int | None = None,
        request_id: str | None = None,
        headers: Mapping[str, str] | None = None,
        http_body: str | None = None,
        json_body: Any = None,
        idempotency_key: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message or ""
        #: Código estable, como ``INSUFFICIENT_BALANCE``. Decidí con esto.
        self.code = code
        #: Detalles del error: ``field``, ``status``, ``reason``… o ``None``.
        self.data = data
        self.http_status = http_status
        #: El ``Raya-Request-Id`` (``req_…``): mandalo si escribís a soporte.
        self.request_id = request_id
        self.headers: Mapping[str, str] = headers if headers is not None else {}
        self.http_body = http_body
        self.json_body = json_body
        #: La Idempotency-Key con la que se mandó el POST: reintentá con la misma.
        self.idempotency_key = idempotency_key
        #: Segundos que pidió esperar el servidor (header ``Retry-After``).
        self.retry_after = retry_after

    @property
    def user_message(self) -> str:
        return self.message

    def __str__(self) -> str:
        text = self.message or "<sin mensaje>"
        if self.code:
            text = f"{text} ({self.code})"
        if self.request_id:
            text = f"Request {self.request_id}: {text}"
        return text

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, http_status={self.http_status!r}, "
            f"code={self.code!r}, request_id={self.request_id!r})"
        )


class APIConnectionError(RayaError):
    """No llegó respuesta: timeout o corte (``code`` es ``TIMEOUT`` o ``NETWORK_ERROR``)."""

    def __init__(
        self, message: str | None = None, *, should_retry: bool = False, **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)
        self.should_retry = should_retry


class InvalidRequestError(RayaError):
    """400, 405, 413: falta un parámetro, sobra uno o tiene un valor inválido."""

    @property
    def param(self) -> str | None:
        """El parámetro que falló (``data.field``)."""
        field = self.data.get("field") if isinstance(self.data, dict) else None
        return field if isinstance(field, str) else None


class NotFoundError(InvalidRequestError):
    """404: no existe o no es de tu cuenta."""


class AuthenticationError(RayaError):
    """401: falta la clave secreta o no es válida."""


class PermissionDeniedError(RayaError):
    """403: la cuenta no puede hacer esta operación o no tiene la API habilitada."""


class ConflictError(RayaError):
    """409: choca con el estado del recurso (por ejemplo, ``PAYMENT_NOT_REFUNDABLE``)."""


class IdempotencyError(ConflictError):
    """409 ``IDEMPOTENCY_KEY_REUSED`` o ``IDEMPOTENCY_KEY_IN_USE``."""


class UnprocessableEntityError(RayaError):
    """422: la request está bien, pero no se pudo hacer (saldo insuficiente, destino inválido…)."""


class RateLimitError(RayaError):
    """429: demasiadas requests. ``retry_after`` dice cuántos segundos esperar."""


class APIError(RayaError):
    """5xx o una respuesta inesperada: falló algo del lado de Raya."""


class SignatureVerificationError(RayaError):
    """La firma de un webhook no es válida."""

    def __init__(
        self, message: str, sig_header: str | None = None, http_body: str | None = None
    ) -> None:
        super().__init__(message, http_body=http_body)
        self.sig_header = sig_header


def error_class(http_status: int, code: str | None) -> type[RayaError]:
    if http_status in (400, 405, 413):
        return InvalidRequestError
    if http_status == 401:
        return AuthenticationError
    if http_status == 403:
        return PermissionDeniedError
    if http_status == 404:
        return NotFoundError
    if http_status == 409:
        if code is not None and code.startswith("IDEMPOTENCY_KEY_"):
            return IdempotencyError
        return ConflictError
    if http_status == 422:
        return UnprocessableEntityError
    if http_status == 429:
        return RateLimitError
    if http_status == 408 or http_status >= 500:
        return APIError
    if 400 <= http_status < 500:
        return InvalidRequestError
    return APIError


def _fallback(http_status: int) -> tuple[str, str]:
    """Código y mensaje para respuestas sin el objeto ``error`` (HTML del edge, body vacío…)."""
    if http_status == 429:
        return (
            "RATE_LIMITED",
            "Superaste el límite de requests. Esperá los segundos que indica Retry-After "
            "y reintentá.",
        )
    if http_status == 408 or http_status >= 500:
        return (
            "INTERNAL_ERROR",
            f"Falló algo del lado de Raya (HTTP {http_status}). Reintentá en unos minutos; "
            "en los POST, con la misma Idempotency-Key.",
        )
    return "INVALID_RESPONSE", f"La API respondió algo inesperado (HTTP {http_status})."


def error_from_response(
    *,
    http_status: int,
    headers: Mapping[str, str],
    body: str,
    idempotency_key: str | None,
) -> RayaError:
    """Arma el error de una respuesta que no es 2xx."""
    try:
        json_body: Any = json.loads(body) if body else None
    except ValueError:
        json_body = None

    code = message = None
    data: dict[str, Any] | None = None
    envelope = json_body.get("error") if isinstance(json_body, dict) else None
    if isinstance(envelope, dict):
        if isinstance(envelope.get("code"), str):
            code = envelope["code"]
        if isinstance(envelope.get("message"), str):
            message = envelope["message"]
        if isinstance(envelope.get("data"), dict):
            data = envelope["data"]
    if code is None:
        code, fallback_message = _fallback(http_status)
        message = message or fallback_message

    cls = error_class(http_status, code)
    return cls(
        message,
        code=code,
        data=data,
        http_status=http_status,
        request_id=headers.get("raya-request-id"),
        headers=headers,
        http_body=body,
        json_body=json_body,
        idempotency_key=idempotency_key,
        retry_after=parse_retry_after(headers.get("retry-after")),
    )
