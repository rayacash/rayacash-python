"""Raya PSP: los clientes de tu empresa, cada uno con un CVU a su nombre (``psp.customer``)."""

from __future__ import annotations

from collections.abc import Coroutine, Mapping
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    overload,
)

from typing_extensions import Literal, Protocol

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._list_object import ListObject
    from rayacash._psp_balance import PspCustomerBalance
    from rayacash._psp_service import PspCustomerService

PspCustomerStatus = Literal[
    "verifying", "pending", "active", "blocked", "closed", "failed", "rejected"
]
PspCustomerPersonType = Literal["F", "J"]
PspCustomerBlockedBy = Literal["account", "raya"]
PspCvuStatus = Literal["active", "closing", "closed"]
PspCustomerDeclineCode = Literal[
    "image_unavailable",
    "image_invalid",
    "document_unreadable",
    "document_sides_mismatch",
    "document_mismatch",
    "identity_not_verified",
    "name_mismatch",
    "selfie_invalid",
    "face_mismatch",
    "verification_unavailable",
    "not_approved",
    "bank_rejected",
    "psp_disabled",
]
#: Las acciones sobre un cliente: ``POST /v1/psp/customers/:id/<acción>``, sin body.
PspCustomerAction = Literal["block", "unblock", "close", "recreate"]

_ACTION_VERBS: dict[str, str] = {
    "block": "bloquear",
    "unblock": "desbloquear",
    "close": "dar de baja su CVU",
    "recreate": "recrear su CVU",
}


def _service(customer: RayaObject | None = None) -> PspCustomerService:
    from rayacash._global import default_requestor
    from rayacash._psp_service import PspCustomerService

    requestor = customer._resolve_requestor() if customer is not None else default_requestor()
    return PspCustomerService(requestor)


def _customer_id(customer: RayaObject, action: PspCustomerAction) -> str:
    customer_id = customer.get("id")
    if not isinstance(customer_id, str) or not customer_id:
        raise ValueError(f"Este PspCustomer no tiene id: no se puede {_ACTION_VERBS[action]}.")
    return customer_id


class _ActionById(Protocol):
    def __call__(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> PspCustomer: ...


class _ActionSelf(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> PspCustomer: ...


class _ActionByIdAsync(Protocol):
    def __call__(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, PspCustomer]: ...


class _ActionSelfAsync(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Coroutine[Any, Any, PspCustomer]: ...


class _CustomerActionMethod:
    """Una acción con dos formas, como ``IdentityVerification.cancel``:
    ``PspCustomer.block(customer_id)`` desde la clase y ``customer.block()`` desde un cliente, con
    el ``RayaClient`` del que vino."""

    def __init__(self, action: PspCustomerAction) -> None:
        self._action: PspCustomerAction = action

    @overload
    def __get__(self, customer: None, owner: type | None = None) -> _ActionById: ...

    @overload
    def __get__(self, customer: PspCustomer, owner: type | None = None) -> _ActionSelf: ...

    def __get__(
        self, customer: PspCustomer | None, owner: type | None = None
    ) -> _ActionById | _ActionSelf:
        action = self._action
        if customer is None:

            def action_by_id(
                customer_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> PspCustomer:
                return _service()._action(action, customer_id, idempotency_key, options)

            return action_by_id

        def action_on_customer(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> PspCustomer:
            return _service(customer)._action(
                action, _customer_id(customer, action), idempotency_key, options
            )

        return action_on_customer


class _CustomerActionAsyncMethod:
    """Como ``_CustomerActionMethod``, para asyncio (``block_async`` y las otras tres)."""

    def __init__(self, action: PspCustomerAction) -> None:
        self._action: PspCustomerAction = action

    @overload
    def __get__(self, customer: None, owner: type | None = None) -> _ActionByIdAsync: ...

    @overload
    def __get__(self, customer: PspCustomer, owner: type | None = None) -> _ActionSelfAsync: ...

    def __get__(
        self, customer: PspCustomer | None, owner: type | None = None
    ) -> _ActionByIdAsync | _ActionSelfAsync:
        action = self._action
        if customer is None:

            async def action_by_id(
                customer_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> PspCustomer:
                return await _service()._action_async(action, customer_id, idempotency_key, options)

            return action_by_id

        async def action_on_customer(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> PspCustomer:
            return await _service(customer)._action_async(
                action, _customer_id(customer, action), idempotency_key, options
            )

        return action_on_customer


class PspCustomer(RayaObject):
    """Un cliente de Raya PSP: una persona o una empresa, clienta de la tuya, con un CVU y un alias
    a su nombre (su CUIL o CUIT).

    Recibe transferencias de cualquier banco o billetera y vos transferís en su nombre con
    ``client.psp.transfers.create(...)``. La plata está en tu cuenta: tu saldo la incluye y cada
    cliente lleva el suyo en ``balance``. Es el mismo objeto que llega en los webhooks
    ``psp.customer.*``. Nunca trae las fotos, los demás datos del registro (como su sexo o su
    nacionalidad) ni el motivo de un bloqueo.
    """

    OBJECT_NAME = "psp.customer"

    class Cvu(RayaObject):
        """El CVU del cliente: el activo o, si no tiene, el último que tuvo."""

        #: El CVU: 22 dígitos.
        account: str
        #: Su alias. Puede ser ``None`` mientras lo asignamos: te avisamos con
        #: ``psp.customer.updated``.
        alias: str | None
        #: El titular con el que lo ve quien transfiere: hasta 40 caracteres, en mayúsculas y sin
        #: acentos.
        holder_name: str
        #: ``active``, ``closing`` (la baja en el banco sigue en curso) o ``closed``.
        status: PspCvuStatus
        #: Cuándo quedó activo (ISO 8601 en UTC).
        created_at: str
        #: Cuándo se dio de baja; ``None`` mientras está activo.
        closed_at: str | None

    class DeclineReason(RayaObject):
        """Por qué no pudimos validar o aprobar al cliente (``rejected``) o crear su CVU
        (``failed``). Decidí con ``code``, no con ``message``."""

        #: En ``rejected``: ``image_unavailable``, ``image_invalid``, ``document_unreadable``,
        #: ``document_sides_mismatch``, ``document_mismatch``, ``identity_not_verified``,
        #: ``name_mismatch``, ``selfie_invalid``, ``face_mismatch``, ``verification_unavailable``
        #: o ``not_approved``. En ``failed``: ``bank_rejected`` o ``psp_disabled``. Pueden sumarse
        #: valores.
        code: PspCustomerDeclineCode
        #: El motivo en palabras, en castellano: puede cambiar.
        message: str

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "cvu": Cvu,
        "decline_reason": DeclineReason,
    }
    _plain_fields: ClassVar[frozenset[str]] = frozenset({"metadata"})

    #: ``pspc_`` y 24 letras o números.
    id: str
    object: Literal["psp.customer"]
    #: ``verifying`` (validamos su identidad o lo estamos revisando), ``pending`` (estamos creando
    #: el CVU o asignando el alias), ``active`` (recibe y envía), ``blocked`` (sigue recibiendo,
    #: pero no envía ni se recrea), ``closed`` (CVU dado de baja: conserva el saldo y el
    #: historial, y se puede recrear), ``failed`` (no pudimos crear el CVU: se puede recrear) o
    #: ``rejected`` (no pudimos validarlo o aprobarlo: es final y libera el CUIL). Pueden sumarse
    #: valores.
    status: PspCustomerStatus
    #: ``F`` (persona humana) o ``J`` (persona jurídica). Con ``identity_verification``, siempre
    #: ``F``.
    person_type: PspCustomerPersonType
    #: Su CUIL o CUIT: 11 dígitos, sin guiones. Con ``identity_verification``, el CUIL de la
    #: verificación.
    tax_id: str
    #: Su nombre y apellido, o su razón social, tal como lo mandaste. Con
    #: ``identity_verification``, su nombre y apellido del RENAPER, tomados de la verificación.
    name: str
    #: Su saldo, en pesos: sube con lo que recibe y baja con lo que transferís en su nombre.
    balance: float
    #: Siempre ``"ARS"``.
    currency: str
    #: Su CVU: el activo o, si no tiene, el último que tuvo; ``None`` si nunca tuvo uno.
    cvu: Cvu | None
    #: Quién lo bloqueó (``account``, vos, o ``raya``; si los dos, ``raya``). ``None`` si su
    #: ``status`` no es ``blocked``.
    blocked_by: PspCustomerBlockedBy | None
    #: El ``id`` de la verificación de Identidad con la que lo creaste (``idv_…``), o ``None``.
    identity_verification: str | None
    #: Por qué se rechazó o falló; ``None`` si su ``status`` no es ``rejected`` ni ``failed``.
    decline_reason: DeclineReason | None
    #: Tu identificador del cliente.
    external_reference: str | None
    #: Tus pares clave-valor (un dict común). ``{}`` si no mandaste ninguno.
    metadata: dict[str, str]
    #: Cuándo lo creaste (ISO 8601 en UTC), como ``"2026-10-24T13:05:10Z"``.
    created_at: str

    #: Lo bloquea: sigue recibiendo, pero no puede enviar ni recrear su CVU.
    #: ``PspCustomer.block(customer_id)`` o ``customer.block()``.
    block = _CustomerActionMethod("block")
    block_async = _CustomerActionAsyncMethod("block")
    #: Levanta tu bloqueo (uno de Raya solo lo levantamos nosotros).
    #: ``PspCustomer.unblock(customer_id)`` o ``customer.unblock()``.
    unblock = _CustomerActionMethod("unblock")
    unblock_async = _CustomerActionAsyncMethod("unblock")
    #: Da de baja su CVU, con su saldo y su historial a salvo.
    #: ``PspCustomer.close(customer_id)`` o ``customer.close()``.
    close = _CustomerActionMethod("close")
    close_async = _CustomerActionAsyncMethod("close")
    #: Le crea un CVU nuevo (desde ``closed`` o ``failed``).
    #: ``PspCustomer.recreate(customer_id)`` o ``customer.recreate()``.
    recreate = _CustomerActionMethod("recreate")
    recreate_async = _CustomerActionAsyncMethod("recreate")

    # --- Estilo global (rayacash.PspCustomer.*); ver PspCustomerService para el detalle. ---

    # create tiene las tres formas de PspCustomerService.create (con Identidad, con las fotos o
    # una persona jurídica); la implementación reenvía a _create, sin sobrecargas, porque mypy no
    # deja pasar valores Optional a una sobrecarga.

    @overload
    @classmethod
    def create(
        cls,
        *,
        identity_verification: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    @classmethod
    def create(
        cls,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["F"],
        document_front_url: str,
        document_back_url: str,
        selfie_url: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    @classmethod
    def create(
        cls,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["J"],
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @classmethod
    def create(
        cls,
        *,
        identity_verification: str | None = None,
        tax_id: str | None = None,
        name: str | None = None,
        person_type: PspCustomerPersonType | None = None,
        document_front_url: str | None = None,
        document_back_url: str | None = None,
        selfie_url: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Crea un cliente con tu clave secreta en ``rayacash.api_key`` (o en
        ``options["api_key"]``): con ``identity_verification``, con las fotos o, una persona
        jurídica, con sus datos. Ver ``client.psp.customers.create``."""
        return _service()._create(
            identity_verification=identity_verification,
            tax_id=tax_id,
            name=name,
            person_type=person_type,
            document_front_url=document_front_url,
            document_back_url=document_back_url,
            selfie_url=selfie_url,
            external_reference=external_reference,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @overload
    @classmethod
    async def create_async(
        cls,
        *,
        identity_verification: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    @classmethod
    async def create_async(
        cls,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["F"],
        document_front_url: str,
        document_back_url: str,
        selfie_url: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    @classmethod
    async def create_async(
        cls,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["J"],
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @classmethod
    async def create_async(
        cls,
        *,
        identity_verification: str | None = None,
        tax_id: str | None = None,
        name: str | None = None,
        person_type: PspCustomerPersonType | None = None,
        document_front_url: str | None = None,
        document_back_url: str | None = None,
        selfie_url: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        return await _service()._create_async(
            identity_verification=identity_verification,
            tax_id=tax_id,
            name=name,
            person_type=person_type,
            document_front_url=document_front_url,
            document_back_url=document_back_url,
            selfie_url=selfie_url,
            external_reference=external_reference,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(cls, customer_id: str, *, options: RequestOptions | None = None) -> PspCustomer:
        return _service().retrieve(customer_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomer:
        return await _service().retrieve_async(customer_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        status: PspCustomerStatus | None = None,
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspCustomer]:
        return _service().list(
            status=status,
            external_reference=external_reference,
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
        status: PspCustomerStatus | None = None,
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspCustomer]:
        return await _service().list_async(
            status=status,
            external_reference=external_reference,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )

    @classmethod
    def retrieve_balance(
        cls, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomerBalance:
        """El saldo de un cliente: ``rayacash.PspCustomer.retrieve_balance(customer_id)``."""
        return _service().retrieve_balance(customer_id, options=options)

    @classmethod
    async def retrieve_balance_async(
        cls, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomerBalance:
        return await _service().retrieve_balance_async(customer_id, options=options)
