from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from rayacash._encoding import Amount, canonical_amount, path_id
from rayacash._payment import Payment
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


def _create_body(
    amount: Amount,
    description: str | None,
    external_reference: str | None,
    return_url: str | None,
    metadata: Mapping[str, str] | None,
) -> dict[str, Any]:
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError('metadata tiene que ser un dict de str a str, como {"cliente_id": "8812"}.')
    return {
        "amount": canonical_amount(amount),
        "description": description,
        "external_reference": external_reference,
        "return_url": return_url,
        "metadata": metadata,
    }


def _refund_path(payment_id: str) -> str:
    return f"/v1/payments/{path_id('payment_id', payment_id)}/refund"


class PaymentService:
    """``client.payments``: cobrar por transferencia con un CVU exclusivo por pago."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
        *,
        amount: Amount,
        description: str | None = None,
        external_reference: str | None = None,
        return_url: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        """Crea un pago ``pending`` con un CVU y un alias exclusivos (``POST /v1/payments``).

        Mostrale a quien paga ``bank_transfer.cvu`` y ``bank_transfer.alias``, o mandalo a
        ``checkout_url``. Te avisamos con ``payment.succeeded`` cuando llega la transferencia.
        Puede tardar hasta 40 s si damos de alta un CVU nuevo (el timeout por defecto es 65 s).

        :param amount: Pesos, hasta 2 decimales, entre 0.01 y 99999999.99.
        :param description: Qué se vendió (hasta 255 caracteres).
        :param external_reference: Tu identificador, como el número de pedido.
        :param return_url: A dónde vuelve quien paga desde ``checkout_url``.
        :param metadata: Hasta 20 pares clave-valor de texto.
        :param idempotency_key: Recomendada: guardala con el pedido y reusala si reintentás.
            Si no la pasás, generamos una que protege los reintentos de esta llamada.
        """
        return cast(
            Payment,
            self._requestor.request(
                "POST",
                "/v1/payments",
                body=_create_body(amount, description, external_reference, return_url, metadata),
                idempotency_key=idempotency_key,
                options=options,
                expected=Payment,
            ),
        )

    async def create_async(
        self,
        *,
        amount: Amount,
        description: str | None = None,
        external_reference: str | None = None,
        return_url: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        """Como ``create()``, para asyncio."""
        return cast(
            Payment,
            await self._requestor.request_async(
                "POST",
                "/v1/payments",
                body=_create_body(amount, description, external_reference, return_url, metadata),
                idempotency_key=idempotency_key,
                options=options,
                expected=Payment,
            ),
        )

    def retrieve(self, payment_id: str, *, options: RequestOptions | None = None) -> Payment:
        """Un pago de tu negocio (``GET /v1/payments/:id``)."""
        path = f"/v1/payments/{path_id('payment_id', payment_id)}"
        return cast(
            Payment, self._requestor.request("GET", path, options=options, expected=Payment)
        )

    async def retrieve_async(
        self, payment_id: str, *, options: RequestOptions | None = None
    ) -> Payment:
        """Como ``retrieve()``, para asyncio."""
        path = f"/v1/payments/{path_id('payment_id', payment_id)}"
        return cast(
            Payment,
            await self._requestor.request_async("GET", path, options=options, expected=Payment),
        )

    def refund(
        self,
        payment_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        """Devuelve todo lo recibido a la cuenta desde la que se pagó (``POST …/refund``).

        Solo pagos ``succeeded``, hasta 30 días después de ``paid_at``. Es total: no hay
        reembolsos parciales. Si la confirmación tarda, sale ``APIError`` con
        ``code == "BANK_UNAVAILABLE"``: reintentá más tarde con la misma ``idempotency_key``
        (nunca se manda dos veces) o esperá el webhook ``payment.refunded``.
        """
        return cast(
            Payment,
            self._requestor.request(
                "POST",
                _refund_path(payment_id),
                idempotency_key=idempotency_key,
                options=options,
                expected=Payment,
            ),
        )

    async def refund_async(
        self,
        payment_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> Payment:
        """Como ``refund()``, para asyncio."""
        return cast(
            Payment,
            await self._requestor.request_async(
                "POST",
                _refund_path(payment_id),
                idempotency_key=idempotency_key,
                options=options,
                expected=Payment,
            ),
        )
