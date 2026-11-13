"""``client.test_helpers``: lo que solo existe en un sandbox, con su clave secreta de prueba.

Las clases se llaman ``Sandbox…`` y no ``Test…``: pytest recolecta las clases ``Test*`` (también
las que importa un módulo de tests), y estas son de producción.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rayacash._connect_order import ConnectOrder
from rayacash._encoding import Amount, canonical_amount, path_id
from rayacash._error import APIError
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


def _simulate_path(payment_id: str) -> str:
    return f"/v1/test/payments/{path_id('payment_id', payment_id)}/simulate_transfer"


def _simulate_body(amount: Amount | None) -> dict[str, Any] | None:
    """Sin ``amount`` no va body, como en un reembolso: la API simula el monto exacto del pago."""
    if amount is None:
        return None
    return {"amount": canonical_amount(amount)}


def _payment_or_order(result: RayaObject) -> Payment | ConnectOrder:
    """El pago como quedó, según su ``object``: un ``Payment`` o, si el id era el de una orden de
    Raya Connect, un ``ConnectOrder`` (``Payment`` es solo el respaldo de un body sin ``object``).
    Otra cosa es una respuesta inesperada y sale con la respuesta, como una lista que no es una
    lista."""
    if isinstance(result, (Payment, ConnectOrder)):
        return result
    response = result.last_response
    assert response is not None
    raise APIError(
        "La API respondió algo que no es un Payment ni un ConnectOrder.",
        code="INVALID_RESPONSE",
        http_status=response.http_status,
        request_id=response.request_id,
        headers=response.headers,
        http_body=response.body,
    )


class SandboxPaymentHelpersService:
    """``client.test_helpers.payments``: simular la transferencia de un pago de prueba.

    Solo existe en un sandbox: usá un ``RayaClient`` con su clave secreta de prueba
    (``raya_sk_test_…``). Con una clave real, la API responde ``PermissionDeniedError`` con
    ``code == "SANDBOX_ONLY"``.
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def simulate_transfer(
        self,
        payment_id: str,
        *,
        amount: Amount | None = None,
        options: RequestOptions | None = None,
    ) -> Payment | ConnectOrder:
        """Simula que llegó la transferencia de un pago de prueba
        (``POST /v1/test/payments/:id/simulate_transfer``). No se mueve plata.

        Pasa lo mismo que en tu cuenta real cuando llega una transferencia: el pago se resuelve
        (si se acredita, lo recibido se suma en el momento al saldo de prueba) y te avisamos con
        los webhooks de siempre (``payment.*``, o ``connect.order.*`` para una orden), con
        ``livemode`` en ``False``.

        Con el ``id`` de una orden de Raya Connect de una app de este sandbox (el de
        ``connect.orders.create``), devuelve el ``ConnectOrder``. Se simula con la clave secreta de
        prueba de la cuenta dueña de la app, no con el access_token del usuario de prueba.

        :param payment_id: El ``id`` del pago, o el de la orden.
        :param amount: Lo que se simula recibir, en pesos (hasta 2 decimales). Sin él, el monto
            exacto. Si es menor que el del pago, queda ``failed`` con ``failure_code`` en
            ``"amount_mismatch"`` (en tu cuenta real, además, se devuelve solo). Si es igual o
            mayor, queda ``succeeded``, con ``amount_received`` en lo simulado.

        No lleva ``idempotency_key``: simular un pago que ya no está ``pending`` (ya simulado o
        vencido) da ``ConflictError`` con ``code == "PAYMENT_NOT_PENDING"`` y el estado en
        ``error.data["status"]``. Si te llega en un reintento, después de un corte de red, la
        primera simulación ya se aplicó: consultá el pago (``payments.retrieve`` o, para una
        orden, ``connect.orders.retrieve``). Un id que no es de este sandbox da ``NotFoundError``
        con ``code == "PAYMENT_NOT_FOUND"``.
        """
        result = self._requestor.request(
            "POST",
            _simulate_path(payment_id),
            body=_simulate_body(amount),
            options=options,
            expected=Payment,
            idempotent=False,
        )
        return _payment_or_order(result)

    async def simulate_transfer_async(
        self,
        payment_id: str,
        *,
        amount: Amount | None = None,
        options: RequestOptions | None = None,
    ) -> Payment | ConnectOrder:
        """Como ``simulate_transfer()``, para asyncio."""
        result = await self._requestor.request_async(
            "POST",
            _simulate_path(payment_id),
            body=_simulate_body(amount),
            options=options,
            expected=Payment,
            idempotent=False,
        )
        return _payment_or_order(result)


class SandboxHelpersService:
    """``client.test_helpers``: lo que solo existe en un sandbox, con su clave secreta de prueba
    (``raya_sk_test_…``). Hoy, ``client.test_helpers.payments.simulate_transfer``.
    """

    payments: SandboxPaymentHelpersService

    def __init__(self, requestor: APIRequestor) -> None:
        self.payments = SandboxPaymentHelpersService(requestor)
