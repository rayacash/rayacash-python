from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rayacash._balance import Balance
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor


class BalanceService:
    """``client.balance``: tu saldo disponible."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def retrieve(self, *, options: RequestOptions | None = None) -> Balance:
        """Tu saldo disponible en pesos (``GET /v1/balance``)."""
        return cast(
            Balance,
            self._requestor.request("GET", "/v1/balance", options=options, expected=Balance),
        )

    async def retrieve_async(self, *, options: RequestOptions | None = None) -> Balance:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            Balance,
            await self._requestor.request_async(
                "GET", "/v1/balance", options=options, expected=Balance
            ),
        )
