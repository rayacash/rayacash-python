"""Los objetos de ejemplo de Raya Connect (api.md › Connect y Usuarios).

Son los mismos JSON que muestra raya.cash/api (utils/apiReferenceRequests.ts y
apiReferenceContent.ts de la web): los tres SDKs testean con los mismos vectores.
"""

from __future__ import annotations

from typing import Any

# La app de ejemplo (Developers › Integraciones › Apps) y su autorización.
APP_CLIENT_ID = "7650337728110670"
APP_CLIENT_SECRET = "raya_cs_live_" + "Qx9Km2Pr4Tv6Wy8Za1Bc3De5Fg7Hj0KnLm2Np4Qr6St8Uv0Wx"
AUTH_CODE = "c0d3ejemploQx9Km2Pr4Tv6Wy8Za1Bc3De5Fg7Hj0Kn"
REDIRECT_URI = "https://tienda.example.com/raya/callback"
# El destino de Developers › Webhooks del dueño de la app.
NOTIFICATION_URL = "we_3fN8kQ2vX7mB1pR5tZ9cW4yD"

# La cuenta conectada: el user_id del access_token.
USER_ID = "9d4f2b7e-3c61-4e0a-9b8f-2a5c7d1e6f40"
ACCESS_TOKEN = "raya_at_live_4mQ8sT2vX7bN1kR5wZ9cH3jLpD6fG0aEyU8iO2pA5sD7fG9h"
# El access_token de la cuenta de prueba de la app (Developers › Apps › tu app › Test): el
# prefijo de prueba, el client_id y 32 caracteres base62. Sintético, como los demás.
TEST_MODE_ACCESS_TOKEN = "raya_at_test_" + APP_CLIENT_ID + "pR5tZ9cW4yD3fN8kQ2vX7mB1hJ6gL0sA"

OAUTH_TOKEN: dict[str, Any] = {
    "object": "oauth_token",
    "access_token": ACCESS_TOKEN,
    "token_type": "Bearer",
    "scope": "orders profile",
    "user_id": USER_ID,
    "expires_in": None,
    "refresh_token": None,
}

USER: dict[str, Any] = {
    "id": USER_ID,
    "object": "user",
    "type": "personal",
    "email": "lucia@almacen.example.com",
    "first_name": "Lucía",
    "last_name": "Ejemplo",
    "full_name": "Lucía Ejemplo",
    "identification": {"type": "DNI", "number": "34567890"},
    "tax_id": "27345678901",
    "phone": "+5493415550123",
    "date_of_birth": "1990-05-17",
    "sex": "F",
    "nationality": "Argentina",
    "address": {
        "street": "Calle Ejemplo",
        "number": "1234",
        "floor": "2",
        "apartment": "B",
        "city": "Rosario",
        "province": "Santa Fe",
        "postal_code": "2000",
        "country": "Argentina",
    },
    "identity_verified": True,
    "verified_at": "2026-10-24T15:35:08Z",
    "business": None,
    "merchant": {"name": "Almacén Ejemplo", "image": None},
    "created_at": "2026-10-24T15:30:12Z",
}

# Una empresa conectada: identification CUIT, business con representante y sin negocio
# configurado todavía (merchant None: se lo creamos con su primer pago).
USER_BUSINESS: dict[str, Any] = {
    **USER,
    "id": "5b1e7c3a-9d2f-4e6b-8a0c-7f3d1b9e2c54",
    "type": "business",
    "email": "admin@proveedora.example.com",
    "first_name": None,
    "last_name": None,
    "full_name": "Proveedora Ejemplo S. A.",
    "identification": {"type": "CUIT", "number": "30123456782"},
    "tax_id": "30123456782",
    "phone": None,
    "date_of_birth": None,
    "sex": None,
    "nationality": None,
    "address": None,
    "business": {
        "legal_name": "Proveedora Ejemplo S. A.",
        "tax_id": "30123456782",
        "company_type": "S.A.",
        "representative": {"first_name": "Juan", "last_name": "Ejemplo", "tax_id": "20123456785"},
    },
    "merchant": None,
}

ORDER_ID = "e7b3a9c2-4d1f-4a8e-b6c0-5f2d9e8a7b61"

# Un pago de Raya Connect recién creado: un ítem de 45000 con una comisión de 500 para la app; a
# la cuenta conectada le quedan 44500. Sin description, queda el title del ítem. La página de
# pago sigue en /checkout/<id>.
ORDER_PENDING: dict[str, Any] = {
    "id": ORDER_ID,
    "object": "connect.order",
    "status": "pending",
    "amount": 45000,
    "fee": 500,
    "net_amount": 44500,
    "amount_received": None,
    "currency": "ARS",
    "items": [{"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}],
    "description": "Pedido 1042",
    "external_reference": "pedido-1042",
    "account": USER_ID,
    "bank_transfer": {"cvu": "0000123390456538582824", "alias": "raya.cash.ejemplo"},
    "checkout_url": f"https://raya.cash/checkout/{ORDER_ID}",
    "back_urls": {
        "success": "https://tienda.example.com/pedidos/1042",
        "failure": "https://tienda.example.com/pedidos/1042/error",
    },
    "auto_return": "approved",
    "notification_url": NOTIFICATION_URL,
    "payer": None,
    "failure_code": None,
    "metadata": {"pedido_id": "1042"},
    "expires_at": "2026-10-25T16:00:00Z",
    "paid_at": None,
    "refunded_at": None,
    "created_at": "2026-10-24T16:00:00Z",
}

# Pagado: pagó la misma cuenta que el pago de ejemplo; fee y net_amount no cambian.
ORDER_SUCCEEDED: dict[str, Any] = {
    **ORDER_PENDING,
    "status": "succeeded",
    "amount_received": 45000,
    "payer": {
        "name": "María Ejemplo",
        "tax_id": "27123456781",
        "account": "0000123300602983525937",
    },
    "paid_at": "2026-10-24T16:07:41Z",
}

# Reembolsado desde la app: se devuelve todo y la comisión se revierte; paid_at se mantiene.
ORDER_REFUNDED: dict[str, Any] = {
    **ORDER_SUCCEEDED,
    "status": "refunded",
    "refunded_at": "2026-10-24T17:20:00Z",
}

EVENT_ORDER_SUCCEEDED: dict[str, Any] = {
    "id": "evt_7pK2mT9xB4vN6rQ1sW8cH5jL",
    "object": "event",
    "type": "connect.order.succeeded",
    "api_version": "2026-10-23",
    "created_at": "2026-10-24T16:07:41Z",
    "data": {"object": ORDER_SUCCEEDED},
}
