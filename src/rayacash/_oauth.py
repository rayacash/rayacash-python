"""El access_token de una cuenta conectada: lo que devuelve ``POST /v1/oauth/token``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing_extensions import Literal

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions
from rayacash._util import mask_key

if TYPE_CHECKING:
    from rayacash._oauth_service import OAuthService


def _service() -> OAuthService:
    from rayacash._global import default_requestor
    from rayacash._oauth_service import OAuthService

    return OAuthService(default_requestor())


class OAuthToken(RayaObject):
    """El access_token de una cuenta de Raya que conectó tu aplicación.

    Guardalo junto a ``user_id`` como guardás tu clave secreta: es la ``api_key`` de un
    ``RayaClient`` para cobrar a nombre de esa cuenta (``client.connect.orders``) y leer sus
    datos (``client.users``). No vence: deja de valer cuando la cuenta desconecta tu app
    (``ACCESS_TOKEN_REVOKED``) o cuando vuelve a autorizarla (se emite uno nuevo).

    ``str()`` y ``repr()`` enmascaran el token (``raya_at_live_…fG9h``), para que no termine
    entero en un log; ``token.access_token``, ``to_dict()`` y ``json.dumps(token)`` lo dan entero.
    """

    OBJECT_NAME = "oauth_token"

    object: Literal["oauth_token"]
    #: ``raya_at_live_…`` (``raya_at_test_…`` si es un usuario de prueba de un sandbox): la
    #: credencial para operar por esa cuenta. Solo en tu servidor.
    access_token: str
    #: Siempre ``"Bearer"``.
    token_type: str
    #: Los permisos que dio la cuenta, separados por espacio (``"orders profile"``).
    scope: str
    #: El id de la cuenta conectada: el de ``client.users.retrieve()`` y el ``account`` de los
    #: pagos que creás a su nombre.
    user_id: str
    #: Hoy siempre ``None``: el token no vence. Viene por las integraciones portadas de Mercado
    #: Pago.
    expires_in: int | None
    #: Hoy siempre ``None``: no hay refresh. Viene por las integraciones portadas de Mercado Pago.
    refresh_token: str | None

    def __str__(self) -> str:
        values = self.to_dict()
        token = values.get("access_token")
        if isinstance(token, str):
            values["access_token"] = mask_key(token)
        return json.dumps(values, sort_keys=True, indent=2, ensure_ascii=False)


class OAuth:
    """Estilo global: ``rayacash.OAuth.token(...)``. Ver ``client.oauth.token()``."""

    @classmethod
    def token(
        cls,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        options: RequestOptions | None = None,
    ) -> OAuthToken:
        """Canjea el ``code`` por el access_token de la cuenta. No necesita ``rayacash.api_key``."""
        return _service().token(client_id, client_secret, code, redirect_uri, options=options)

    @classmethod
    async def token_async(
        cls,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        options: RequestOptions | None = None,
    ) -> OAuthToken:
        return await _service().token_async(
            client_id, client_secret, code, redirect_uri, options=options
        )
