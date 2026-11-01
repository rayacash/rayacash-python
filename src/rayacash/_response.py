"""La respuesta HTTP detrás de cada objeto (``obj.last_response``)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RayaResponse:
    """Status, headers y body crudos de la última respuesta de la API para un objeto."""

    __slots__ = ("body", "data", "headers", "http_status", "idempotency_key", "request_id")

    def __init__(
        self,
        *,
        http_status: int,
        headers: Mapping[str, str],
        body: str,
        data: Any,
        idempotency_key: str | None,
    ) -> None:
        self.http_status = http_status
        #: Headers de la respuesta (sin distinguir mayúsculas).
        self.headers = headers
        self.body = body
        #: El JSON ya parseado.
        self.data = data
        #: El ``Raya-Request-Id`` (``req_…``). En un replay idempotente es uno nuevo.
        self.request_id: str | None = headers.get("raya-request-id")
        #: La Idempotency-Key que mandamos (solo en los POST).
        self.idempotency_key = idempotency_key

    def __repr__(self) -> str:
        return f"<RayaResponse http_status={self.http_status} request_id={self.request_id!r}>"
