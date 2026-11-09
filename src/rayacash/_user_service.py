from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rayacash._encoding import path_id
from rayacash._request_options import RequestOptions
from rayacash._user import User

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


class UserService:
    """``client.users``: los datos de las cuentas que conectaron tu aplicación."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def retrieve(self, user_id: str, *, options: RequestOptions | None = None) -> User:
        """Una cuenta conectada a tu app (``GET /v1/users/:id``).

        Con el access_token de esa cuenta: ``user_id`` es el ``user_id`` que vino con el token,
        o ``"me"``. Cualquier otro id da ``NotFoundError`` con ``code == "USER_NOT_FOUND"``.
        """
        path = f"/v1/users/{path_id('user_id', user_id)}"
        return cast(User, self._requestor.request("GET", path, options=options, expected=User))

    async def retrieve_async(self, user_id: str, *, options: RequestOptions | None = None) -> User:
        """Como ``retrieve()``, para asyncio."""
        path = f"/v1/users/{path_id('user_id', user_id)}"
        return cast(
            User, await self._requestor.request_async("GET", path, options=options, expected=User)
        )
