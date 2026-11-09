from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from typing_extensions import Literal

from rayacash._checkout import Checkout
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
            "expires_in tiene que ser un int: los segundos hasta que vence el checkout "
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


def _order_path(checkout_id: str) -> str:
    return f"/v1/checkout/orders/{path_id('checkout_id', checkout_id)}"


class CheckoutOrderService:
    """``client.checkout.orders``: los checkouts que tu app crea a nombre de una cuenta conectada.

    Usá un ``RayaClient`` con el access_token de esa cuenta (``raya_at_live_…``), no con tu clave.
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
    ) -> Checkout:
        """Crea un checkout a nombre de la cuenta conectada (``POST /v1/checkout/orders``).

        Nace ``pending``, con un CVU y un alias exclusivos. Mandá a quien paga a ``checkout_url``
        (o mostrale ``bank_transfer``). Al acreditarse,
        ``net_amount`` se liquida a la cuenta conectada y ``fee`` a la tuya; te avisamos con
        ``checkout.succeeded`` (y a la cuenta conectada, con ``payment.succeeded``). Puede tardar
        hasta 40 s si damos de alta un CVU nuevo (el timeout por defecto es 65 s).

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
            Webhooks, que recibe los ``checkout.*`` de este checkout. Sin él, los suscriptos.
        :param expires_in: Segundos hasta que vence, de 300 a 864000 (10 días). Por defecto,
            el plazo del comercio conectado.
        :param idempotency_key: Recomendada: guardala con el pedido y reusala si reintentás.
            Si no la pasás, generamos una que protege los reintentos de esta llamada.
        """
        return cast(
            Checkout,
            self._requestor.request(
                "POST",
                "/v1/checkout/orders",
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
                expected=Checkout,
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
    ) -> Checkout:
        """Como ``create()``, para asyncio."""
        return cast(
            Checkout,
            await self._requestor.request_async(
                "POST",
                "/v1/checkout/orders",
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
                expected=Checkout,
            ),
        )

    def retrieve(self, checkout_id: str, *, options: RequestOptions | None = None) -> Checkout:
        """Un checkout de tu app a nombre de esta cuenta (``GET /v1/checkout/orders/:id``)."""
        return cast(
            Checkout,
            self._requestor.request(
                "GET", _order_path(checkout_id), options=options, expected=Checkout
            ),
        )

    async def retrieve_async(
        self, checkout_id: str, *, options: RequestOptions | None = None
    ) -> Checkout:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            Checkout,
            await self._requestor.request_async(
                "GET", _order_path(checkout_id), options=options, expected=Checkout
            ),
        )

    def refund(
        self,
        checkout_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Checkout:
        """Devuelve todo lo recibido a la cuenta desde la que se pagó (``POST …/refund``).

        Solo checkouts ``succeeded``, hasta 30 días después de ``paid_at``. Es total: la cuenta
        conectada devuelve ``net_amount`` y tu comisión se revierte. Si la confirmación tarda,
        sale ``APIError`` con ``code == "BANK_UNAVAILABLE"``: reintentá más tarde con la misma
        ``idempotency_key`` (nunca se manda dos veces) o esperá el webhook ``checkout.refunded``.
        """
        return cast(
            Checkout,
            self._requestor.request(
                "POST",
                _order_path(checkout_id) + "/refund",
                idempotency_key=idempotency_key,
                options=options,
                expected=Checkout,
            ),
        )

    async def refund_async(
        self,
        checkout_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Checkout:
        """Como ``refund()``, para asyncio."""
        return cast(
            Checkout,
            await self._requestor.request_async(
                "POST",
                _order_path(checkout_id) + "/refund",
                idempotency_key=idempotency_key,
                options=options,
                expected=Checkout,
            ),
        )


class CheckoutService:
    """``client.checkout``: hoy, ``client.checkout.orders``."""

    orders: CheckoutOrderService

    def __init__(self, requestor: APIRequestor) -> None:
        self.orders = CheckoutOrderService(requestor)
