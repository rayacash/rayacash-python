from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rayacash._connect_payout import ConnectPayout, ConnectPayoutStatus
from rayacash._encoding import (
    Amount,
    canonical_amount,
    encode_query,
    path_id,
    validate_idempotency_key,
)
from rayacash._list_object import ListObject
from rayacash._request_options import RequestOptions

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
            "connect.payouts.create necesita idempotency_key: generá un UUID v4, guardalo con "
            "la operación antes de llamar y reusalo en cada reintento."
        )
    return validate_idempotency_key(value)


def _payout_path(payout_id: str) -> str:
    return f"/v1/connect/payouts/{path_id('payout_id', payout_id)}"


def _list_query(
    status: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "status": status,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


class ConnectPayoutService:
    """``client.connect.payouts``: lo que les enviás a los vendedores de tu plataforma.

    Usá un ``RayaClient`` con tu clave secreta (``raya_sk_live_…``), no con el access_token de
    una cuenta conectada: la plata sale de tu saldo.
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> ConnectPayout:
        """Envía pesos desde tu saldo a un vendedor (``POST /v1/connect/payouts``).

        Sale por la cuenta de tu negocio. Descontamos ``amount`` de tu saldo apenas lo creás y
        la cuenta de destino recibe ``net_amount``, que es ``amount`` menos ``processing_fee``.
        Buscamos al titular del destino y te lo devolvemos en ``counterparty``: no hay paso de
        confirmación, así que revisá el destino antes de llamar. Si el destino es una cuenta de
        Raya, vuelve ``completed``; si no, ``pending`` hasta que te avisamos con
        ``transfer.sent`` o ``transfer.failed``, con el mismo ``id``. Si falla, te devolvemos
        ``amount`` entero, incluida la comisión.

        :param amount: Lo que sale de tu saldo, en pesos, hasta 2 decimales (``60000``,
            ``Decimal("60000.50")``). La comisión se descuenta de acá.
        :param destination: CBU o CVU (22 dígitos) o alias (6 a 20 caracteres). No mandes el
            CUIT o CUIL del titular: lo buscamos nosotros.
        :param idempotency_key: Obligatoria. Un UUID v4 que guardás con la operación **antes**
            de llamar y reusás en cada reintento: así nunca se envía dos veces. Para volver a
            intentar un payout que terminó ``failed``, usá una clave nueva.
        """
        return cast(
            ConnectPayout,
            self._requestor.request(
                "POST",
                "/v1/connect/payouts",
                body=_create_body(amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=ConnectPayout,
            ),
        )

    async def create_async(
        self,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> ConnectPayout:
        """Como ``create()``, para asyncio."""
        return cast(
            ConnectPayout,
            await self._requestor.request_async(
                "POST",
                "/v1/connect/payouts",
                body=_create_body(amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=ConnectPayout,
            ),
        )

    def retrieve(self, payout_id: str, *, options: RequestOptions | None = None) -> ConnectPayout:
        """Un payout de tu cuenta (``GET /v1/connect/payouts/:id``)."""
        return cast(
            ConnectPayout,
            self._requestor.request(
                "GET", _payout_path(payout_id), options=options, expected=ConnectPayout
            ),
        )

    async def retrieve_async(
        self, payout_id: str, *, options: RequestOptions | None = None
    ) -> ConnectPayout:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            ConnectPayout,
            await self._requestor.request_async(
                "GET", _payout_path(payout_id), options=options, expected=ConnectPayout
            ),
        )

    def list(
        self,
        *,
        status: ConnectPayoutStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[ConnectPayout]:
        """Tus payouts, del más nuevo al más viejo (``GET /v1/connect/payouts``).

        Devuelve una página. Para recorrer todos: ``.auto_paging_iter()``.

        :param status: ``pending``, ``completed``, ``failed`` o ``reversed``.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _list_query(status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[ConnectPayout]",
            self._requestor.request_list("/v1/connect/payouts", query=query, options=options),
        )

    async def list_async(
        self,
        *,
        status: ConnectPayoutStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[ConnectPayout]:
        """Como ``list()``, para asyncio."""
        query = _list_query(status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[ConnectPayout]",
            await self._requestor.request_list_async(
                "/v1/connect/payouts", query=query, options=options
            ),
        )
