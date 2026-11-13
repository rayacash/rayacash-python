from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Literal

from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._connect_payout_service import ConnectPayoutService
    from rayacash._list_object import ListObject

ConnectPayoutStatus = Literal["pending", "completed", "failed", "reversed"]


def _service() -> ConnectPayoutService:
    from rayacash._connect_payout_service import ConnectPayoutService
    from rayacash._global import default_requestor

    return ConnectPayoutService(default_requestor())


class ConnectPayout(RayaObject):
    """Un payout de Raya Connect: pesos que le enviás a un vendedor de tu plataforma.

    Sale de tu saldo, por la cuenta de tu negocio, y se crea con tu clave secreta (no con el
    access_token de una cuenta conectada). ``amount`` es lo que sale de tu saldo y la cuenta de
    destino recibe ``net_amount``. Es también una transferencia: aparece en ``transfers.list()``
    y llega en los webhooks ``transfer.*``, con el mismo ``id``, ``amount`` y ``processing_fee``
    como ``fee``.
    """

    OBJECT_NAME = "connect.payout"

    class Origin(RayaObject):
        """La cuenta de tu negocio desde la que sale el payout."""

        #: CVU de origen: 22 dígitos.
        account: str
        #: Alias de esa cuenta, si tiene.
        alias: str | None
        #: El nombre con el que la ve quien recibe la transferencia.
        name: str

    class Counterparty(RayaObject):
        """A quién le enviaste: el titular que encontramos al validar el destino."""

        #: Nombre del titular.
        name: str | None
        #: CUIT o CUIL del titular: 11 dígitos, sin guiones.
        tax_id: str | None
        #: CBU o CVU de destino: 22 dígitos.
        account: str | None
        #: Alias de la cuenta, si lo conocemos.
        alias: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "origin": Origin,
        "counterparty": Counterparty,
    }

    #: Identificador del payout. Es también el ``id`` de la transferencia que lo representa.
    id: str
    object: Literal["connect.payout"]
    #: ``pending`` (se está procesando), ``completed`` (se acreditó en la cuenta de destino),
    #: ``failed`` (no se pudo completar) o ``reversed`` (la entidad de destino lo revirtió).
    #: En ``failed`` y ``reversed`` te devolvimos ``amount`` entero a tu saldo, incluida la
    #: comisión. Pueden sumarse valores.
    status: ConnectPayoutStatus
    #: Lo que sale de tu saldo, en pesos: lo que mandaste en ``amount``.
    amount: float
    #: La comisión de este payout, en pesos. Puede ser ``0``. Si falla o se revierte, te la
    #: devolvemos y este campo se mantiene.
    processing_fee: float
    #: Lo que recibe la cuenta de destino: ``amount`` menos ``processing_fee``.
    net_amount: float
    #: Siempre ``"ARS"``.
    currency: str
    origin: Origin
    counterparty: Counterparty
    #: El identificador del payout en la red de transferencias, para rastrearlo con la otra
    #: entidad. Es ``None`` mientras está ``pending``, si falló y cuando el destino es una
    #: cuenta de Raya.
    reference: str | None
    #: Cuándo lo creaste (ISO 8601 en UTC), como ``"2026-10-24T17:40:06Z"``.
    created_at: str

    # --- Estilo global (rayacash.ConnectPayout.*); ver ConnectPayoutService para el detalle. ---

    @classmethod
    def create(
        cls,
        *,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> ConnectPayout:
        """Envía pesos desde tu saldo a un CBU, CVU o alias, con tu clave secreta en
        ``rayacash.api_key`` (o en ``options["api_key"]``). ``idempotency_key`` es obligatoria."""
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
    ) -> ConnectPayout:
        return await _service().create_async(
            amount=amount, destination=destination, idempotency_key=idempotency_key, options=options
        )

    @classmethod
    def retrieve(cls, payout_id: str, *, options: RequestOptions | None = None) -> ConnectPayout:
        return _service().retrieve(payout_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, payout_id: str, *, options: RequestOptions | None = None
    ) -> ConnectPayout:
        return await _service().retrieve_async(payout_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        status: ConnectPayoutStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[ConnectPayout]:
        return _service().list(
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
        status: ConnectPayoutStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[ConnectPayout]:
        return await _service().list_async(
            status=status,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )
