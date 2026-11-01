from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rayacash._encoding import (
    Amount,
    canonical_amount,
    encode_query,
    path_id,
    validate_idempotency_key,
)
from rayacash._list_object import ListObject
from rayacash._request_options import RequestOptions
from rayacash._transfer import Transfer, TransferDirection, TransferStatus

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


def _create_body(amount: Amount, destination: str) -> dict[str, Any]:
    if not isinstance(destination, str):
        raise TypeError(
            "destination tiene que ser un str (CBU, CVU o alias): "
            "un CBU como número pierde los ceros de adelante."
        )
    return {"amount": canonical_amount(amount), "destination": destination}


def _required_idempotency_key(value: object) -> str:
    if value is None:
        raise TypeError(
            "transfers.create necesita idempotency_key: generá un UUID v4, guardalo con la "
            "operación antes de llamar y reusalo en cada reintento."
        )
    return validate_idempotency_key(value)


def _list_query(
    direction: str | None,
    status: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "direction": direction,
            "status": status,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


class TransferService:
    """``client.transfers``: enviar pesos y consultar las transferencias enviadas y recibidas."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Transfer:
        """Envía pesos desde tu saldo a un CBU, CVU o alias (``POST /v1/transfers``).

        Buscamos al titular del destino y te lo devolvemos en ``counterparty``. Si el destino es
        una cuenta de Raya, vuelve ``completed``; si no, ``pending`` hasta que te avisamos con
        ``transfer.sent`` o ``transfer.failed``.

        :param amount: Pesos, hasta 2 decimales (``25000``, ``Decimal("25000.50")``).
        :param destination: CBU o CVU (22 dígitos) o alias (6 a 20 caracteres).
        :param idempotency_key: Obligatoria. Un UUID v4 que guardás con la operación **antes**
            de llamar y reusás en cada reintento: así nunca se transfiere dos veces. Para volver
            a intentar una transferencia que terminó ``failed``, usá una clave nueva.
        """
        return cast(
            Transfer,
            self._requestor.request(
                "POST",
                "/v1/transfers",
                body=_create_body(amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=Transfer,
            ),
        )

    async def create_async(
        self,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Transfer:
        """Como ``create()``, para asyncio."""
        return cast(
            Transfer,
            await self._requestor.request_async(
                "POST",
                "/v1/transfers",
                body=_create_body(amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=Transfer,
            ),
        )

    def retrieve(self, transfer_id: str, *, options: RequestOptions | None = None) -> Transfer:
        """Una transferencia, enviada o recibida (``GET /v1/transfers/:id``)."""
        path = f"/v1/transfers/{path_id('transfer_id', transfer_id)}"
        return cast(
            Transfer, self._requestor.request("GET", path, options=options, expected=Transfer)
        )

    async def retrieve_async(
        self, transfer_id: str, *, options: RequestOptions | None = None
    ) -> Transfer:
        """Como ``retrieve()``, para asyncio."""
        path = f"/v1/transfers/{path_id('transfer_id', transfer_id)}"
        return cast(
            Transfer,
            await self._requestor.request_async("GET", path, options=options, expected=Transfer),
        )

    def list(
        self,
        *,
        direction: TransferDirection | None = None,
        status: TransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Transfer]:
        """Tus transferencias, de la más nueva a la más vieja (``GET /v1/transfers``).

        Devuelve una página. Para recorrer todas: ``.auto_paging_iter()``.

        :param direction: ``inbound`` (recibidas) u ``outbound`` (enviadas).
        :param status: ``pending``, ``completed``, ``failed`` o ``reversed``.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _list_query(direction, status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[Transfer]",
            self._requestor.request_list("/v1/transfers", query=query, options=options),
        )

    async def list_async(
        self,
        *,
        direction: TransferDirection | None = None,
        status: TransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Transfer]:
        """Como ``list()``, para asyncio."""
        query = _list_query(direction, status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[Transfer]",
            await self._requestor.request_list_async("/v1/transfers", query=query, options=options),
        )
