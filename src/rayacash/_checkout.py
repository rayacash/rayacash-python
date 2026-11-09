from __future__ import annotations

from collections.abc import Coroutine, Mapping, Sequence
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
    from rayacash._checkout_service import CheckoutOrderService

CheckoutStatus = Literal["pending", "succeeded", "failed", "expired", "refunded"]


def _service(checkout: RayaObject | None = None) -> CheckoutOrderService:
    from rayacash._checkout_service import CheckoutOrderService
    from rayacash._global import default_requestor

    requestor = checkout._resolve_requestor() if checkout is not None else default_requestor()
    return CheckoutOrderService(requestor)


def _checkout_id(checkout: RayaObject) -> str:
    checkout_id = checkout.get("id")
    if not isinstance(checkout_id, str) or not checkout_id:
        raise ValueError("Este Checkout no tiene id: no se puede reembolsar.")
    return checkout_id


class _RefundById(Protocol):
    def __call__(
        self,
        checkout_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Checkout: ...


class _RefundSelf(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Checkout: ...


class _RefundByIdAsync(Protocol):
    def __call__(
        self,
        checkout_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, Checkout]: ...


class _RefundSelfAsync(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Coroutine[Any, Any, Checkout]: ...


class _RefundMethod:
    """``Checkout.refund(checkout_id)`` desde la clase y ``checkout.refund()`` desde un checkout."""

    @overload
    def __get__(self, checkout: None, owner: type | None = None) -> _RefundById: ...

    @overload
    def __get__(self, checkout: Checkout, owner: type | None = None) -> _RefundSelf: ...

    def __get__(
        self, checkout: Checkout | None, owner: type | None = None
    ) -> _RefundById | _RefundSelf:
        if checkout is None:

            def refund_by_id(
                checkout_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> Checkout:
                return _service().refund(
                    checkout_id, idempotency_key=idempotency_key, options=options
                )

            return refund_by_id

        def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> Checkout:
            return _service(checkout).refund(
                _checkout_id(checkout), idempotency_key=idempotency_key, options=options
            )

        return refund


class _RefundAsyncMethod:
    @overload
    def __get__(self, checkout: None, owner: type | None = None) -> _RefundByIdAsync: ...

    @overload
    def __get__(self, checkout: Checkout, owner: type | None = None) -> _RefundSelfAsync: ...

    def __get__(
        self, checkout: Checkout | None, owner: type | None = None
    ) -> _RefundByIdAsync | _RefundSelfAsync:
        if checkout is None:

            async def refund_by_id(
                checkout_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> Checkout:
                return await _service().refund_async(
                    checkout_id, idempotency_key=idempotency_key, options=options
                )

            return refund_by_id

        async def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> Checkout:
            return await _service(checkout).refund_async(
                _checkout_id(checkout), idempotency_key=idempotency_key, options=options
            )

        return refund


class Checkout(RayaObject):
    """Un cobro que tu app crea a nombre de una cuenta conectada, con tu comisión fija (``fee``).

    Quien paga transfiere a un CVU exclusivo (``bank_transfer``) o paga en ``checkout_url``, la
    página con el nombre y la imagen del comercio conectado. Al acreditarse, ``net_amount`` se
    liquida a la cuenta conectada y ``fee`` a la tuya. Entregá solo cuando ``status`` es
    ``succeeded``. El ``id`` es el del pago: la cuenta conectada lo ve con su propia clave.

    Los ítems se leen con ``checkout["items"]`` (una lista de ``Checkout.Item``): como todo
    ``RayaObject`` es un ``dict``, ``checkout.items`` es el método ``items()`` de ``dict``.
    """

    OBJECT_NAME = "checkout"

    class Item(RayaObject):
        """Un ítem del checkout."""

        title: str
        quantity: int
        #: El precio unitario, en pesos.
        unit_price: float

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
        #: CBU o CVU de origen: si reembolsás el checkout, el dinero vuelve acá.
        account: str | None

    class BackUrls(RayaObject):
        """A dónde vuelve quien paga desde ``checkout_url``. Siempre las dos claves."""

        success: str | None
        failure: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "items": Item,
        "bank_transfer": BankTransfer,
        "payer": Payer,
        "back_urls": BackUrls,
    }
    _plain_fields: ClassVar[frozenset[str]] = frozenset({"metadata"})

    id: str
    object: Literal["checkout"]
    #: ``pending``, ``succeeded``, ``failed``, ``expired`` o ``refunded`` (pueden sumarse valores).
    status: CheckoutStatus
    #: Cuánto tiene que transferir quien paga, en pesos: la suma de los ítems.
    amount: float
    #: Tu comisión fija, en pesos. Se liquida a la cuenta dueña de la app.
    fee: float
    #: ``amount`` menos ``fee``: lo que se liquida a la cuenta conectada.
    net_amount: float
    #: Cuánto recibimos (``None`` hasta que llega una transferencia).
    amount_received: float | None
    #: Siempre ``"ARS"``.
    currency: str
    # items: list[Item] -> se lee con checkout["items"]: el atributo es dict.items(). Anotarlo
    # acá le mentiría al type checker (y pisa el método para mypy y pyright).
    description: str | None
    #: Tu identificador del checkout (por ejemplo, el número de pedido).
    external_reference: str | None
    #: El ``user_id`` de la cuenta conectada a cuyo nombre se cobra.
    account: str
    bank_transfer: BankTransfer
    #: Nuestra página de pago, con el nombre y la imagen del comercio conectado.
    checkout_url: str
    back_urls: BackUrls
    #: ``"approved"`` si quien paga vuelve solo a ``back_urls.success`` al acreditarse; si no,
    #: ``None``.
    auto_return: Literal["approved"] | None
    #: El destino de Developers › Webhooks (``we_…``) que recibe los eventos de este checkout,
    #: o ``None`` (los suscriptos a ``checkout.*``).
    notification_url: str | None
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

    #: Reembolsa el checkout completo. ``Checkout.refund(checkout_id)`` o ``checkout.refund()``.
    refund = _RefundMethod()
    refund_async = _RefundAsyncMethod()

    # --- Estilo global (rayacash.Checkout.*); ver CheckoutOrderService para el detalle. ---

    @classmethod
    def create(
        cls,
        *,
        items: Sequence[Mapping[str, Any]],
        fee: Amount | None = None,
        description: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        back_urls: Mapping[str, str] | None = None,
        auto_return: Literal["approved"] | None = None,
        notification_url: str | None = None,
        expires_in: int | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Checkout:
        """Crea un checkout a nombre de la cuenta conectada cuyo access_token está en
        ``rayacash.api_key`` (o en ``options["api_key"]``)."""
        return _service().create(
            items=items,
            fee=fee,
            description=description,
            external_reference=external_reference,
            metadata=metadata,
            back_urls=back_urls,
            auto_return=auto_return,
            notification_url=notification_url,
            expires_in=expires_in,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    async def create_async(
        cls,
        *,
        items: Sequence[Mapping[str, Any]],
        fee: Amount | None = None,
        description: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        back_urls: Mapping[str, str] | None = None,
        auto_return: Literal["approved"] | None = None,
        notification_url: str | None = None,
        expires_in: int | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Checkout:
        return await _service().create_async(
            items=items,
            fee=fee,
            description=description,
            external_reference=external_reference,
            metadata=metadata,
            back_urls=back_urls,
            auto_return=auto_return,
            notification_url=notification_url,
            expires_in=expires_in,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(cls, checkout_id: str, *, options: RequestOptions | None = None) -> Checkout:
        return _service().retrieve(checkout_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, checkout_id: str, *, options: RequestOptions | None = None
    ) -> Checkout:
        return await _service().retrieve_async(checkout_id, options=options)
