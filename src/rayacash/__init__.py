"""El SDK oficial de Python para la API de Raya Cash.

Estilo cliente (el recomendado)::

    import rayacash

    client = rayacash.RayaClient()  # lee la clave secreta de RAYA_SECRET_KEY
    payment = client.payments.create(amount=15000, description="Pedido #1042")

Estilo global, como stripe-python::

    rayacash.api_key = os.environ["RAYA_SECRET_KEY"]
    payment = rayacash.Payment.create(amount=15000)

Apps y cuentas conectadas (cobrar a nombre de otra cuenta con tu comisión)::

    token = client.oauth.token(client_id, client_secret, code, redirect_uri)
    connected = rayacash.RayaClient(token.access_token)  # raya_at_live_…
    checkout = connected.checkout.orders.create(items=[...], fee=500)

Referencia de la API: https://raya.cash/api
"""

from __future__ import annotations

import httpx
from typing_extensions import Literal

from rayacash._requestor import DEFAULT_API_BASE, DEFAULT_MAX_NETWORK_RETRIES, DEFAULT_TIMEOUT
from rayacash._util import AppInfo, validate_app_info
from rayacash._version import VERSION

__version__ = VERSION

# --- Configuración del estilo global -------------------------------------------------------
# Solo la usan rayacash.Balance / Transfer / Payment / OAuth / User / Checkout. Un RayaClient
# tiene la suya, salvo el logging (log y RAYA_LOG), que vale para todo el proceso.

#: Tu clave secreta (raya_sk_live_…) o el access_token de una cuenta conectada (raya_at_live_…).
#: Si es None, se lee de la variable de entorno RAYA_SECRET_KEY.
api_key: str | None = None
api_base: str = DEFAULT_API_BASE
max_network_retries: int = DEFAULT_MAX_NETWORK_RETRIES
#: Segundos por intento o un httpx.Timeout.
timeout: float | httpx.Timeout = DEFAULT_TIMEOUT
#: Clientes httpx propios para el estilo global (proxies, certificados…). No los cerramos.
http_client: httpx.Client | None = None
async_http_client: httpx.AsyncClient | None = None
app_info: AppInfo | None = None
#: "info" o "debug" para ver las requests en stderr (también con RAYA_LOG). Vale para todo el
#: proceso, también para cada RayaClient, y gana sobre RAYA_LOG.
log: Literal["debug", "info"] | None = None


def set_app_info(name: str, *, version: str | None = None, url: str | None = None) -> None:
    """Identifica tu plugin en el User-Agent del estilo global (lo ves en Developers › Logs)."""
    global app_info
    info: AppInfo = {"name": name}
    if version is not None:
        info["version"] = version
    if url is not None:
        info["url"] = url
    app_info = validate_app_info(info)


from rayacash._balance import Balance  # noqa: E402
from rayacash._checkout import Checkout, CheckoutStatus  # noqa: E402
from rayacash._client import RayaClient  # noqa: E402
from rayacash._encoding import Amount  # noqa: E402
from rayacash._error import (  # noqa: E402
    APIConnectionError,
    APIError,
    AuthenticationError,
    ConflictError,
    IdempotencyError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RayaError,
    SignatureVerificationError,
    UnprocessableEntityError,
)
from rayacash._event import Event, EventType  # noqa: E402
from rayacash._list_object import AnyIterator, ListObject  # noqa: E402
from rayacash._oauth import OAuth, OAuthToken  # noqa: E402
from rayacash._payment import Payment, PaymentStatus  # noqa: E402
from rayacash._raya_object import RayaObject  # noqa: E402
from rayacash._request_options import RequestOptions  # noqa: E402
from rayacash._response import RayaResponse  # noqa: E402
from rayacash._transfer import Transfer, TransferDirection, TransferStatus  # noqa: E402
from rayacash._user import User, UserType  # noqa: E402
from rayacash._webhook import Webhook, WebhookSignature  # noqa: E402

__all__ = [
    "DEFAULT_API_BASE",
    "VERSION",
    "APIConnectionError",
    "APIError",
    "Amount",
    "AnyIterator",
    "AppInfo",
    "AuthenticationError",
    "Balance",
    "Checkout",
    "CheckoutStatus",
    "ConflictError",
    "Event",
    "EventType",
    "IdempotencyError",
    "InvalidRequestError",
    "ListObject",
    "NotFoundError",
    "OAuth",
    "OAuthToken",
    "Payment",
    "PaymentStatus",
    "PermissionDeniedError",
    "RateLimitError",
    "RayaClient",
    "RayaError",
    "RayaObject",
    "RayaResponse",
    "RequestOptions",
    "SignatureVerificationError",
    "Transfer",
    "TransferDirection",
    "TransferStatus",
    "UnprocessableEntityError",
    "User",
    "UserType",
    "Webhook",
    "WebhookSignature",
    "__version__",
    "api_base",
    "api_key",
    "app_info",
    "async_http_client",
    "http_client",
    "log",
    "max_network_retries",
    "set_app_info",
    "timeout",
]
