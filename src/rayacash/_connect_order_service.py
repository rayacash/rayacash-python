from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast, overload

from typing_extensions import Literal, deprecated

from rayacash._connect_order import ConnectOrder
from rayacash._connect_payout_service import ConnectPayoutService
from rayacash._deprecated import accepts_checkout_id, accepts_checkout_id_async
from rayacash._encoding import Amount, canonical_amount, path_id
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


def _items_body(items: object) -> list[dict[str, Any]]:
    """Los ítems tal como vienen, con ``unit_price`` como ``Decimal`` exacto (igual que ``amount``).

    Lo demás (claves, cantidades, rangos) lo valida la API: una clave de más da
    ``PARAMETER_UNKNOWN`` con el campo, como ``items[0].sku``.
    """
    if isinstance(items, (str, bytes, Mapping)) or not isinstance(items, Sequence):
        raise TypeError(
            "items tiene que ser una lista de dicts con title, quantity y unit_price, como "
            '[{"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}].'
        )
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"items[{index}] tiene que ser un dict con title, quantity y unit_price."
            )
        body: dict[str, Any] = dict(item)
        if body.get("unit_price") is not None:
            body["unit_price"] = canonical_amount(body["unit_price"], f"items[{index}].unit_price")
        result.append(body)
    return result


def _create_body(
    items: Sequence[Mapping[str, Any]],
    fee: Amount | None,
    description: str | None,
    external_reference: str | None,
    metadata: Mapping[str, str] | None,
    back_urls: Mapping[str, str] | None,
    auto_return: str | None,
    notification_url: str | None,
    expires_in: int | None,
) -> dict[str, Any]:
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError('metadata tiene que ser un dict de str a str, como {"pedido_id": "1042"}.')
    if back_urls is not None and not isinstance(back_urls, Mapping):
        raise TypeError(
            "back_urls tiene que ser un dict con success y/o failure, como "
            '{"success": "https://tienda.example.com/pedidos/1042"}.'
        )
    if expires_in is not None and (isinstance(expires_in, bool) or not isinstance(expires_in, int)):
        raise TypeError(
            "expires_in tiene que ser un int: los segundos hasta que vence el pago "
            "(de 300 a 864000)."
        )
    return {
        "items": _items_body(items),
        "fee": canonical_amount(fee, "fee") if fee is not None else None,
        "description": description,
        "external_reference": external_reference,
        "metadata": metadata,
        "back_urls": back_urls,
        "auto_return": auto_return,
        "notification_url": notification_url,
        "expires_in": expires_in,
    }


def _order_path(order_id: str) -> str:
    return f"/v1/connect/orders/{path_id('order_id', order_id)}"


class ConnectOrderService:
    """``client.connect.orders``: los pagos que tu app crea a nombre de una cuenta conectada.

    Usá un ``RayaClient`` con el access_token de esa cuenta (``raya_at_live_…``), no con tu clave.

    ``retrieve`` y ``refund`` aceptan también ``checkout_id=``, el nombre de la 1.1.0 (deprecado,
    se va en la 2.0.0): por eso tienen un ``@overload`` con ``@deprecated``.
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
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
        """Crea un pago a nombre de la cuenta conectada (``POST /v1/connect/orders``).

        Nace ``pending``, con un CVU y un alias exclusivos. Mandá a quien paga a ``checkout_url``
        (o mostrale ``bank_transfer``). Al acreditarse,
        ``net_amount`` se liquida a la cuenta conectada y ``fee`` a la tuya; te avisamos con
        ``connect.order.succeeded`` (y a la cuenta conectada, con ``payment.succeeded``). Puede
        tardar hasta 40 s si damos de alta un CVU nuevo (el timeout por defecto es 65 s).

        :param items: De 1 a 20 dicts ``{"title", "quantity", "unit_price"}``; el total es la
            suma de ``quantity × unit_price``. ``unit_price`` en pesos, hasta 2 decimales.
        :param fee: Tu comisión fija en pesos (no un porcentaje), de 0 a menos que el total.
            Por defecto, 0.
        :param description: Qué se vendió (hasta 255 caracteres). Por defecto, el título del
            ítem (o «<título> y N más»).
        :param external_reference: Tu identificador, como el número de pedido.
        :param metadata: Hasta 20 pares clave-valor de texto.
        :param back_urls: ``{"success": url, "failure": url}``: a dónde vuelve quien paga.
        :param auto_return: ``"approved"`` para que quien paga vuelva solo a
            ``back_urls.success`` al acreditarse.
        :param notification_url: El id (``we_…``) o la URL de un destino tuyo de Developers ›
            Webhooks, que recibe los ``connect.order.*`` de este pago. Sin él, los suscriptos.
        :param expires_in: Segundos hasta que vence, de 300 a 864000 (10 días). Por defecto,
            el plazo del comercio conectado.
        :param idempotency_key: Recomendada: guardala con el pedido y reusala si reintentás.
            Si no la pasás, generamos una que protege los reintentos de esta llamada.
        """
        return cast(
            ConnectOrder,
            self._requestor.request(
                "POST",
                "/v1/connect/orders",
                body=_create_body(
                    items,
                    fee,
                    description,
                    external_reference,
                    metadata,
                    back_urls,
                    auto_return,
                    notification_url,
                    expires_in,
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=ConnectOrder,
            ),
        )

    async def create_async(
        self,
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
        """Como ``create()``, para asyncio."""
        return cast(
            ConnectOrder,
            await self._requestor.request_async(
                "POST",
                "/v1/connect/orders",
                body=_create_body(
                    items,
                    fee,
                    description,
                    external_reference,
                    metadata,
                    back_urls,
                    auto_return,
                    notification_url,
                    expires_in,
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=ConnectOrder,
            ),
        )

    @overload
    def retrieve(self, order_id: str, *, options: RequestOptions | None = None) -> ConnectOrder: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    def retrieve(
        self, *, checkout_id: str, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @accepts_checkout_id
    def retrieve(self, order_id: str, *, options: RequestOptions | None = None) -> ConnectOrder:
        """Un pago de tu app a nombre de esta cuenta (``GET /v1/connect/orders/:id``)."""
        return cast(
            ConnectOrder,
            self._requestor.request(
                "GET", _order_path(order_id), options=options, expected=ConnectOrder
            ),
        )

    @overload
    async def retrieve_async(
        self, order_id: str, *, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    async def retrieve_async(
        self, *, checkout_id: str, options: RequestOptions | None = None
    ) -> ConnectOrder: ...

    @accepts_checkout_id_async
    async def retrieve_async(
        self, order_id: str, *, options: RequestOptions | None = None
    ) -> ConnectOrder:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            ConnectOrder,
            await self._requestor.request_async(
                "GET", _order_path(order_id), options=options, expected=ConnectOrder
            ),
        )

    @overload
    def refund(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    def refund(
        self,
        *,
        checkout_id: str,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder: ...

    @accepts_checkout_id
    def refund(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder:
        """Devuelve todo lo recibido a la cuenta desde la que se pagó (``POST …/refund``).

        Solo pagos ``succeeded``, hasta 30 días después de ``paid_at``. Es total: la cuenta
        conectada devuelve ``net_amount`` y tu comisión se revierte. Si la confirmación tarda,
        sale ``APIError`` con ``code == "BANK_UNAVAILABLE"``: reintentá más tarde con la misma
        ``idempotency_key`` (nunca se manda dos veces) o esperá el webhook
        ``connect.order.refunded``.
        """
        return cast(
            ConnectOrder,
            self._requestor.request(
                "POST",
                _order_path(order_id) + "/refund",
                idempotency_key=idempotency_key,
                options=options,
                expected=ConnectOrder,
            ),
        )

    @overload
    async def refund_async(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder: ...

    @overload
    @deprecated("checkout_id está deprecado desde la 1.2.0 y se va en la 2.0.0: usá order_id.")
    async def refund_async(
        self,
        *,
        checkout_id: str,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder: ...

    @accepts_checkout_id_async
    async def refund_async(
        self,
        order_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> ConnectOrder:
        """Como ``refund()``, para asyncio."""
        return cast(
            ConnectOrder,
            await self._requestor.request_async(
                "POST",
                _order_path(order_id) + "/refund",
                idempotency_key=idempotency_key,
                options=options,
                expected=ConnectOrder,
            ),
        )


class ConnectService:
    """``client.connect``: Raya Connect.

    ``client.connect.orders`` (pagos a nombre de una cuenta conectada) va con el access_token de
    esa cuenta; ``client.connect.payouts`` (lo que enviás a tus vendedores), con tu clave secreta.
    """

    orders: ConnectOrderService
    payouts: ConnectPayoutService

    def __init__(self, requestor: APIRequestor) -> None:
        self.orders = ConnectOrderService(requestor)
        self.payouts = ConnectPayoutService(requestor)
