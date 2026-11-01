from __future__ import annotations

from collections.abc import Coroutine, Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    overload,
)

from typing_extensions import Literal, Protocol

from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._payment_service import PaymentService

PaymentStatus = Literal["pending", "succeeded", "failed", "expired", "refunded"]


def _service(payment: RayaObject | None = None) -> PaymentService:
    from rayacash._global import default_requestor
    from rayacash._payment_service import PaymentService

    requestor = payment._resolve_requestor() if payment is not None else default_requestor()
    return PaymentService(requestor)


def _payment_id(payment: RayaObject) -> str:
    payment_id = payment.get("id")
    if not isinstance(payment_id, str) or not payment_id:
        raise ValueError("Este Payment no tiene id: no se puede reembolsar.")
    return payment_id


class _RefundById(Protocol):
    def __call__(
        self,
        payment_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Payment: ...


class _RefundSelf(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Payment: ...


class _RefundByIdAsync(Protocol):
    def __call__(
        self,
        payment_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, Payment]: ...


class _RefundSelfAsync(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Coroutine[Any, Any, Payment]: ...


class _RefundMethod:
    """``Payment.refund(payment_id)`` desde la clase y ``payment.refund()`` desde un pago."""

    @overload
    def __get__(self, payment: None, owner: type | None = None) -> _RefundById: ...

    @overload
    def __get__(self, payment: Payment, owner: type | None = None) -> _RefundSelf: ...

    def __get__(
        self, payment: Payment | None, owner: type | None = None
    ) -> _RefundById | _RefundSelf:
        if payment is None:

            def refund_by_id(
                payment_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> Payment:
                return _service().refund(
                    payment_id, idempotency_key=idempotency_key, options=options
                )

            return refund_by_id

        def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> Payment:
            return _service(payment).refund(
                _payment_id(payment), idempotency_key=idempotency_key, options=options
            )

        return refund


class _RefundAsyncMethod:
    @overload
    def __get__(self, payment: None, owner: type | None = None) -> _RefundByIdAsync: ...

    @overload
    def __get__(self, payment: Payment, owner: type | None = None) -> _RefundSelfAsync: ...

    def __get__(
        self, payment: Payment | None, owner: type | None = None
    ) -> _RefundByIdAsync | _RefundSelfAsync:
        if payment is None:

            async def refund_by_id(
                payment_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> Payment:
                return await _service().refund_async(
                    payment_id, idempotency_key=idempotency_key, options=options
                )

            return refund_by_id

        async def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> Payment:
            return await _service(payment).refund_async(
                _payment_id(payment), idempotency_key=idempotency_key, options=options
            )

        return refund


class Payment(RayaObject):
    """Un cobro único por transferencia bancaria, con un CVU y un alias exclusivos.

    Entregá el pedido solo cuando ``status`` es ``succeeded``. Mientras está ``pending``, el CVU
    y el alias son exclusivos de este pago; cuando deja de estarlo, dejá de mostrarlos.
    """

    OBJECT_NAME = "payment"

    class BankTransfer(RayaObject):
        """Los datos para pagar por transferencia."""

        #: El CVU al que hay que transferir: 22 dígitos.
        cvu: str
        #: El alias del CVU. Si es ``None``, mostrá solo el CVU.
        alias: str | None

    class Payer(RayaObject):
        """Quién transfirió, con los datos que informa su entidad."""

        name: str | None
        tax_id: str | None
        #: CBU o CVU de origen: si reembolsás el pago, el dinero vuelve acá.
        account: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "bank_transfer": BankTransfer,
        "payer": Payer,
    }
    _plain_fields: ClassVar[frozenset[str]] = frozenset({"metadata"})

    id: str
    object: Literal["payment"]
    #: ``pending``, ``succeeded``, ``failed``, ``expired`` o ``refunded`` (pueden sumarse valores).
    status: PaymentStatus
    #: Cuánto tiene que transferir quien paga, en pesos.
    amount: float
    #: Cuánto recibimos (``None`` hasta que llega una transferencia).
    amount_received: float | None
    #: Siempre ``"ARS"``.
    currency: str
    description: str | None
    #: Tu identificador del pago (por ejemplo, el número de pedido).
    external_reference: str | None
    bank_transfer: BankTransfer
    #: Nuestra página de pago, que se actualiza sola cuando llega la transferencia.
    checkout_url: str
    return_url: str | None
    payer: Payer | None
    #: ``amount_mismatch`` si transfirieron de menos; ``None`` si no falló.
    failure_code: Literal["amount_mismatch"] | None
    #: Tus pares clave-valor (un dict común). ``{}`` si no mandaste ninguno.
    metadata: dict[str, str]
    #: Hasta cuándo se puede pagar (ISO 8601 en UTC).
    expires_at: str
    paid_at: str | None
    refunded_at: str | None
    created_at: str

    #: Reembolsa el pago completo. ``Payment.refund(payment_id)`` o ``payment.refund()``.
    refund = _RefundMethod()
    refund_async = _RefundAsyncMethod()

    # --- Estilo global (rayacash.Payment.*); ver PaymentService para el detalle. ---

    @classmethod
    def create(
        cls,
        *,
        amount: Amount,
        description: str | None = None,
        external_reference: str | None = None,
        return_url: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        """Crea un pago con un CVU exclusivo. Usá un timeout de al menos 60 s (es el default)."""
        return _service().create(
            amount=amount,
            description=description,
            external_reference=external_reference,
            return_url=return_url,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    async def create_async(
        cls,
        *,
        amount: Amount,
        description: str | None = None,
        external_reference: str | None = None,
        return_url: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        return await _service().create_async(
            amount=amount,
            description=description,
            external_reference=external_reference,
            return_url=return_url,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(cls, payment_id: str, *, options: RequestOptions | None = None) -> Payment:
        return _service().retrieve(payment_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, payment_id: str, *, options: RequestOptions | None = None
    ) -> Payment:
        return await _service().retrieve_async(payment_id, options=options)
