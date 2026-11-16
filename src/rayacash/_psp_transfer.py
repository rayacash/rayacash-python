"""Raya PSP: las transferencias de los clientes de tu empresa (``psp.transfer``)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Literal

from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._list_object import ListObject
    from rayacash._psp_service import PspTransferService

PspTransferDirection = Literal["inbound", "outbound"]
PspTransferStatus = Literal["pending", "completed", "failed", "reversed"]


def _service() -> PspTransferService:
    from rayacash._global import default_requestor
    from rayacash._psp_service import PspTransferService

    return PspTransferService(default_requestor())


class PspTransfer(RayaObject):
    """Una transferencia de un cliente de Raya PSP: una que recibió en su CVU (``inbound``) o una
    que enviaste en su nombre (``outbound``).

    Es el mismo objeto que llega en los webhooks ``psp.transfer.*``. Las transferencias de tus
    clientes no aparecen en ``client.transfers.list()`` ni emiten ``transfer.*``.
    """

    OBJECT_NAME = "psp.transfer"

    class Counterparty(RayaObject):
        """La otra parte: quien le transfirió a tu cliente o a quien le transferiste en su
        nombre."""

        #: Nombre del titular.
        name: str | None
        #: CUIT o CUIL del titular: 11 dígitos, sin guiones.
        tax_id: str | None
        #: CBU o CVU: 22 dígitos.
        account: str | None
        #: Alias de la cuenta, si lo conocemos.
        alias: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {"counterparty": Counterparty}

    #: ``pspt_`` y 24 letras o números.
    id: str
    object: Literal["psp.transfer"]
    #: El ``id`` del cliente (``pspc_…``).
    customer: str
    #: ``inbound``: la recibió tu cliente. ``outbound``: la enviaste en su nombre.
    direction: PspTransferDirection
    #: ``pending`` (solo una enviada a otra entidad, mientras se procesa), ``completed``,
    #: ``failed`` o ``reversed`` (la otra entidad la revirtió). Pueden sumarse valores.
    status: PspTransferStatus
    #: Lo que se movió en el saldo de tu cliente, en pesos: el monto entero.
    amount: float
    #: La comisión, en pesos: se descuenta de tu saldo, no del de tu cliente. Es ``0`` entre
    #: clientes de tu cuenta. Si falla o se revierte, te la devolvemos y este campo se mantiene.
    fee: float
    #: ``amount`` menos ``fee``: en una enviada, lo que recibió el destino; en una recibida, lo que
    #: se sumó a tu saldo.
    net_amount: float
    #: Siempre ``"ARS"``.
    currency: str
    #: El CVU de tu cliente que se usó: el de origen en una enviada y el de destino en una recibida.
    account: str
    counterparty: Counterparty
    #: ``"Transferencia"`` en una enviada y en una recibida de otra cuenta de Raya; en una recibida
    #: de otra entidad, el concepto que informó su banco, o ``None``.
    description: str | None
    #: El identificador en la red de transferencias, para rastrearla con la otra entidad. Es
    #: ``None`` mientras está ``pending``, si falló y en las transferencias entre cuentas de Raya.
    reference: str | None
    #: Cuándo se creó (ISO 8601 en UTC), como ``"2026-10-24T15:20:31Z"``.
    created_at: str

    # --- Estilo global (rayacash.PspTransfer.*); ver PspTransferService para el detalle. ---

    @classmethod
    def create(
        cls,
        *,
        customer: str,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> PspTransfer:
        """Transfiere en nombre de un cliente, con tu clave secreta en ``rayacash.api_key`` (o en
        ``options["api_key"]``). ``idempotency_key`` es obligatoria."""
        return _service().create(
            customer=customer,
            amount=amount,
            destination=destination,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    async def create_async(
        cls,
        *,
        customer: str,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> PspTransfer:
        return await _service().create_async(
            customer=customer,
            amount=amount,
            destination=destination,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(cls, transfer_id: str, *, options: RequestOptions | None = None) -> PspTransfer:
        return _service().retrieve(transfer_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, transfer_id: str, *, options: RequestOptions | None = None
    ) -> PspTransfer:
        return await _service().retrieve_async(transfer_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        customer: str | None = None,
        direction: PspTransferDirection | None = None,
        status: PspTransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspTransfer]:
        return _service().list(
            customer=customer,
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
        customer: str | None = None,
        direction: PspTransferDirection | None = None,
        status: PspTransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspTransfer]:
        return await _service().list_async(
            customer=customer,
            direction=direction,
            status=status,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )
