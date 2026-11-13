"""Los objetos de ejemplo de un sandbox: pagos de prueba, una orden simulada y un evento.

Tienen la forma de las respuestas reales de la API a un pago de prueba: el CVU de prueba
(``00000002…``, 22 dígitos que no son de ninguna cuenta), el alias ``sandbox.no.transferir``,
``checkout_url`` en ``/sandbox/pay/<id>`` y el pagador de prueba, siempre el mismo. Los valores
son sintéticos, como los demás.
"""

from __future__ import annotations

from typing import Any

# La clave secreta de prueba de un sandbox: el prefijo de prueba y 48 caracteres base62.
SANDBOX_KEY = "raya_sk_test_" + "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"

SANDBOX_ALIAS = "sandbox.no.transferir"
SANDBOX_PAYER: dict[str, Any] = {
    "name": "Pagador de prueba",
    "tax_id": "20000000001",
    "account": "0000000200000000000001",
}

SANDBOX_PAYMENT_ID = "5d2c8e14-7a3b-4f69-9e05-b1c4d7a2f830"

# Recién creado con payments.create y la clave de prueba: el CVU de prueba del sandbox, vence a
# las 24 horas.
SANDBOX_PAYMENT_PENDING: dict[str, Any] = {
    "id": SANDBOX_PAYMENT_ID,
    "object": "payment",
    "status": "pending",
    "amount": 2500,
    "amount_received": None,
    "currency": "ARS",
    "description": "Pedido 1043",
    "external_reference": "pedido-1043",
    "bank_transfer": {"cvu": "0000000271940365218453", "alias": SANDBOX_ALIAS},
    "checkout_url": f"https://raya.cash/sandbox/pay/{SANDBOX_PAYMENT_ID}",
    "return_url": None,
    "payer": None,
    "failure_code": None,
    "metadata": {},
    "expires_at": "2026-11-12T14:42:33Z",
    "paid_at": None,
    "refunded_at": None,
    "created_at": "2026-11-11T14:42:34Z",
}

# Simulado sin amount: el monto exacto.
SANDBOX_PAYMENT_SUCCEEDED: dict[str, Any] = {
    **SANDBOX_PAYMENT_PENDING,
    "status": "succeeded",
    "amount_received": 2500,
    "payer": SANDBOX_PAYER,
    "paid_at": "2026-11-11T14:43:02Z",
}

# Simulado con menos (amount=1000): failed con amount_mismatch y sin paid_at. En un sandbox no se
# devuelve solo (en la cuenta real, sí: pasa a refunded).
SANDBOX_PAYMENT_FAILED: dict[str, Any] = {
    **SANDBOX_PAYMENT_PENDING,
    "status": "failed",
    "amount_received": 1000,
    "payer": SANDBOX_PAYER,
    "failure_code": "amount_mismatch",
}

# Simulado con más (amount=4000): succeeded, con amount_received en lo simulado.
SANDBOX_PAYMENT_OVERPAID: dict[str, Any] = {**SANDBOX_PAYMENT_SUCCEEDED, "amount_received": 4000}

# Una orden de Raya Connect de una app del sandbox, a nombre de un usuario de prueba, simulada con
# la clave secreta de prueba de la cuenta dueña de la app: el connect.order de siempre, con el CVU
# de prueba del usuario de prueba. Al usuario de prueba le quedan 1490; a la app, 10.
SANDBOX_ORDER_ID = "8a1f3c5e-2d47-4b96-a0e8-6c9b7d3e1f52"
SANDBOX_TEST_USER_ID = "3e9b6a20-5c1d-4f87-8b3a-d42e7f0c9a16"

SANDBOX_ORDER_SUCCEEDED: dict[str, Any] = {
    "id": SANDBOX_ORDER_ID,
    "object": "connect.order",
    "status": "succeeded",
    "amount": 1500,
    "fee": 10,
    "net_amount": 1490,
    "amount_received": 1500,
    "currency": "ARS",
    "items": [{"title": "Pedido 7", "quantity": 1, "unit_price": 1500}],
    "description": "Pedido 7",
    "external_reference": None,
    "account": SANDBOX_TEST_USER_ID,
    "bank_transfer": {"cvu": "0000000238516094726185", "alias": SANDBOX_ALIAS},
    "checkout_url": f"https://raya.cash/checkout/{SANDBOX_ORDER_ID}",
    "back_urls": {"success": None, "failure": None},
    "auto_return": None,
    "notification_url": None,
    "payer": SANDBOX_PAYER,
    "failure_code": None,
    "metadata": {},
    "expires_at": "2026-11-12T14:42:36Z",
    "paid_at": "2026-11-11T14:42:36Z",
    "refunded_at": None,
    "created_at": "2026-11-11T14:42:36Z",
}

# El evento de un sandbox: livemode en false, entre created_at y data (el orden del sobre). Los de
# la cuenta real lo traen en true, y los creados antes de que la API lo sumara no lo traen
# (EVENT_PAYMENT_SUCCEEDED, de tests/fixtures.py).
EVENT_SANDBOX_PAYMENT_SUCCEEDED: dict[str, Any] = {
    "id": "evt_9sB3nQ7wK2xV5mR8tL1cZ4hJ",
    "object": "event",
    "type": "payment.succeeded",
    "api_version": "2026-10-23",
    "created_at": "2026-11-11T14:43:02Z",
    "livemode": False,
    "data": {"object": SANDBOX_PAYMENT_SUCCEEDED},
}
