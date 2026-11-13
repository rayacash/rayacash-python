from __future__ import annotations

from collections.abc import Coroutine, Mapping, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    overload,
)

from typing_extensions import Literal, Protocol, deprecated

from rayacash._deprecated import accepts_checkout_id, accepts_checkout_id_async
from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._connect_order_service import ConnectOrderService

ConnectOrderStatus = Literal["pending", "succeeded", "failed", "expired", "refunded"]


def _service(order: RayaObject | None = None) -> ConnectOrderService:
    from rayacash._connect_order_service import ConnectOrderService
    from rayacash._global import default_requestor

    requestor = order._resolve_requestor() if order is not None else default_requestor()
    return ConnectOrderService(requestor)


def _order_id(order: RayaObject) -> str:
    order_id = order.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise ValueError("Este ConnectOrder no tiene id: no se puede reembolsar.")
    return order_id


# Los de la clase aceptan también checkout_id=, el nombre de la 1.1.0 (deprecado, se va en la
# 2.0.0): el segundo @overload.
class _RefundById(Protocol):
    @overload
    def __call__(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> ConnectOrder: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    def __call__(
        self,
        *,
        checkout_id: str,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> ConnectOrder: ...


class _RefundSelf(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> ConnectOrder: ...


class _RefundByIdAsync(Protocol):
    @overload
    def __call__(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, ConnectOrder]: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    def __call__(
        self,
        *,
        checkout_id: str,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, ConnectOrder]: ...


class _RefundSelfAsync(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Coroutine[Any, Any, ConnectOrder]: ...


class _RefundMethod:
    """``ConnectOrder.refund(order_id)`` desde la clase y ``order.refund()`` desde un pago."""

    @overload
    def __get__(self, order: None, owner: type | None = None) -> _RefundById: ...

    @overload
    def __get__(self, order: ConnectOrder, owner: type | None = None) -> _RefundSelf: ...

    def __get__(
        self, order: ConnectOrder | None, owner: type | None = None
    ) -> _RefundById | _RefundSelf:
        if order is None:

            @accepts_checkout_id
            def refund_by_id(
                order_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> ConnectOrder:
                return _service().refund(order_id, idempotency_key=idempotency_key, options=options)

            return refund_by_id

        def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> ConnectOrder:
            return _service(order).refund(
                _order_id(order), idempotency_key=idempotency_key, options=options
            )

        return refund


class _RefundAsyncMethod:
    @overload
    def __get__(self, order: None, owner: type | None = None) -> _RefundByIdAsync: ...

    @overload
    def __get__(self, order: ConnectOrder, owner: type | None = None) -> _RefundSelfAsync: ...

    def __get__(
        self, order: ConnectOrder | None, owner: type | None = None
    ) -> _RefundByIdAsync | _RefundSelfAsync:
        if order is None:

            @accepts_checkout_id_async
            async def refund_by_id(
                order_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> ConnectOrder:
                return await _service().refund_async(
                    order_id, idempotency_key=idempotency_key, options=options
                )

            return refund_by_id

        async def refund(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> ConnectOrder:
            return await _service(order).refund_async(
                _order_id(order), idempotency_key=idempotency_key, options=options
            )

        return refund


class ConnectOrder(RayaObject):
    """Un pago de Raya Connect: a nombre de una cuenta conectada y con tu comisión fija (``fee``).

    Quien paga transfiere a un CVU exclusivo (``bank_transfer``) o paga en ``checkout_url``, la
    página con el nombre y la imagen del comercio conectado. Al acreditarse, ``net_amount`` se
    liquida a la cuenta conectada y ``fee`` a la tuya. Entregá solo cuando ``status`` es
    ``succeeded``. El ``id`` es también el de su ``Payment``: la cuenta conectada lo ve con su
    propia clave.

    Los ítems se leen con ``order["items"]`` (una lista de ``ConnectOrder.Item``): como todo
    ``RayaObject`` es un ``dict``, ``order.items`` es el método ``items()`` de ``dict``.
    """

    OBJECT_NAME = "connect.order"

    class Item(RayaObject):
        """Un ítem del pago."""

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
        #: CBU o CVU de origen: si reembolsás el pago, el dinero vuelve acá.
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
    #: ``"connect.order"``. ``"checkout"`` es legacy, su nombre en la 1.1.0: la API ya no lo manda
    #: y solo vuelve en un evento de antes del cambio que reenviás desde el dashboard.
    object: Literal["connect.order", "checkout"]
    #: ``pending``, ``succeeded``, ``failed``, ``expired`` o ``refunded`` (pueden sumarse valores).
    status: ConnectOrderStatus
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
    # items: list[Item] -> se lee con order["items"]: el atributo es dict.items(). Anotarlo
    # acá le mentiría al type checker (y pisa el método para mypy y pyright).
    description: str | None
    #: Tu identificador del pago (por ejemplo, el número de pedido).
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
    #: El destino de Developers › Webhooks (``we_…``) que recibe los eventos de este pago, o
    #: ``None`` (los suscriptos a ``connect.order.*``).
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

    #: Reembolsa el pago completo. ``ConnectOrder.refund(order_id)`` o ``order.refund()``.
    refund = _RefundMethod()
    refund_async = _RefundAsyncMethod()

    # --- Estilo global (rayacash.ConnectOrder.*); ver ConnectOrderService para el detalle. ---

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
    ) -> ConnectOrder:
        """Crea un pago a nombre de la cuenta conectada cuyo access_token está en
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
    ) -> ConnectOrder:
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

    # retrieve acepta también checkout_id=, el nombre de la 1.1.0 (deprecado, se va en la 2.0.0).

    @overload
    @classmethod
    def retrieve(cls, order_id: str, *, options: RequestOptions | None = None) -> ConnectOrder: ...

    @overload
    @classmethod
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    def retrieve(
        cls, *, checkout_id: str, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @classmethod
    @accepts_checkout_id
    def retrieve(cls, order_id: str, *, options: RequestOptions | None = None) -> ConnectOrder:
        return _service().retrieve(order_id, options=options)

    @overload
    @classmethod
    async def retrieve_async(
        cls, order_id: str, *, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @overload
    @classmethod
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    async def retrieve_async(
        cls, *, checkout_id: str, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @classmethod
    @accepts_checkout_id_async
    async def retrieve_async(
        cls, order_id: str, *, options: RequestOptions | None = None
    ) -> ConnectOrder:
        return await _service().retrieve_async(order_id, options=options)
