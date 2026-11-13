from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rayacash._oauth import OAuthToken
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor

#: El único grant que existe: lo pone el SDK, no vos.
GRANT_TYPE = "authorization_code"

_HINTS = {
    "client_id": 'el número de tu aplicación, como "7650337728110670"',
    "client_secret": (
        "raya_cs_live_…, de Developers › Apps, o raya_cs_test_…, el de una app de un sandbox"
    ),
    "code": "el code que llegó a la query de tu redirect_uri",
    "redirect_uri": "la misma URL del link de autorización",
}


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} tiene que ser un str ({_HINTS[name]}), no {type(value).__name__}.")
    return value


def _token_body(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    return {
        "client_id": _text("client_id", client_id),
        "client_secret": _text("client_secret", client_secret),
        "grant_type": GRANT_TYPE,
        "code": _text("code", code),
        "redirect_uri": _text("redirect_uri", redirect_uri),
    }


class OAuthService:
    """``client.oauth``: canjear el code de autorización por el access_token de la cuenta."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def token(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        options: RequestOptions | None = None,
    ) -> OAuthToken:
        """Canjea el ``code`` por el access_token de la cuenta (``POST /v1/oauth/token``).

        Es la única request sin ``Authorization``: tu app se identifica con ``client_id`` y
        ``client_secret``, así que el ``RayaClient`` puede no tener clave. Tampoco lleva
        ``Idempotency-Key``: el ``code`` se canjea una sola vez (si falla con
        ``OAUTH_GRANT_INVALID``, ya se usó, venció o la ``redirect_uri`` no coincide). Guardá
        ``token.access_token`` y ``token.user_id`` como guardás tu clave secreta.

        :param client_id: El número de tu aplicación (16 dígitos), de Developers › Apps.
        :param client_secret: ``raya_cs_live_…`` (``raya_cs_test_…``, el de una app de un
            sandbox). Solo en tu servidor, nunca en el navegador.
        :param code: El ``code`` que llegó a la query de tu ``redirect_uri``. Dura 10 minutos.
        :param redirect_uri: Exactamente la misma URL del link de autorización.
        """
        return cast(
            OAuthToken,
            self._requestor.request(
                "POST",
                "/v1/oauth/token",
                body=_token_body(client_id, client_secret, code, redirect_uri),
                options=options,
                expected=OAuthToken,
                authenticated=False,
            ),
        )

    async def token_async(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        options: RequestOptions | None = None,
    ) -> OAuthToken:
        """Como ``token()``, para asyncio."""
        return cast(
            OAuthToken,
            await self._requestor.request_async(
                "POST",
                "/v1/oauth/token",
                body=_token_body(client_id, client_secret, code, redirect_uri),
                options=options,
                expected=OAuthToken,
                authenticated=False,
            ),
        )
