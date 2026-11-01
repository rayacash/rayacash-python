from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Literal

from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._list_object import ListObject
    from rayacash._transfer_service import TransferService

TransferDirection = Literal["inbound", "outbound"]
TransferStatus = Literal["pending", "completed", "failed", "reversed"]


def _service() -> TransferService:
    from rayacash._global import default_requestor
    from rayacash._transfer_service import TransferService

    return TransferService(default_requestor())


class Transfer(RayaObject):
    """Una transferencia: enviada (``outbound``) o recibida (``inbound``, un depósito).

    Es el mismo objeto que llega en los webhooks ``transfer.*``. Los cobros de tus pagos no son
    transferencias: se siguen en cada ``Payment``.
    """

    OBJECT_NAME = "transfer"

    class Counterparty(RayaObject):
        """La otra cuenta, con los datos que informa su entidad."""

        #: Nombre del titular.
        name: str | None
        #: CUIT o CUIL del titular: 11 dígitos, sin guiones.
        tax_id: str | None
        #: CBU o CVU: 22 dígitos.
        account: str | None
        #: Alias de la cuenta, si lo conocemos.
        alias: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {"counterparty": Counterparty}

    id: str
    object: Literal["transfer"]
    #: ``inbound``: la recibiste. ``outbound``: la enviaste.
    direction: TransferDirection
    #: ``pending``, ``completed``, ``failed`` o ``reversed`` (pueden sumarse valores).
    status: TransferStatus
    #: El monto en pesos. En las recibidas, antes de la comisión.
    amount: float
    #: La comisión que te cobramos.
    fee: float
    #: ``amount`` menos ``fee``. En las recibidas, lo que se sumó a tu saldo.
    net_amount: float
    #: Siempre ``"ARS"``.
    currency: str
    counterparty: Counterparty
    description: str | None
    #: El identificador en la red de transferencias (``None`` mientras está ``pending``).
    reference: str | None
    #: Fecha ISO 8601 en UTC, como ``"2026-10-24T13:58:12Z"``.
    created_at: str

    # --- Estilo global (rayacash.Transfer.*); ver TransferService para el detalle. ---

    @classmethod
    def create(
        cls,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Transfer:
        """Envía pesos a un CBU, CVU o alias. ``idempotency_key`` es obligatoria."""
        return _service().create(
            amount=amount, destination=destination, idempotency_key=idempotency_key, options=options
        )

    @classmethod
    async def create_async(
        cls,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Transfer:
        return await _service().create_async(
            amount=amount, destination=destination, idempotency_key=idempotency_key, options=options
        )

    @classmethod
    def retrieve(cls, transfer_id: str, *, options: RequestOptions | None = None) -> Transfer:
        return _service().retrieve(transfer_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, transfer_id: str, *, options: RequestOptions | None = None
    ) -> Transfer:
        return await _service().retrieve_async(transfer_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        direction: TransferDirection | None = None,
        status: TransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Transfer]:
        return _service().list(
            direction=direction,
            status=status,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )

    @classmethod
    async def list_async(
        cls,
        *,
        direction: TransferDirection | None = None,
        status: TransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Transfer]:
        return await _service().list_async(
            direction=direction,
            status=status,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )
