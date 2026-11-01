from __future__ import annotations

from typing_extensions import Literal

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions


class Balance(RayaObject):
    """Tu saldo disponible, en pesos.

    Ya tiene descontadas las transferencias que enviaste, aunque sigan ``pending``.
    """

    OBJECT_NAME = "balance"

    object: Literal["balance"]
    #: Saldo disponible en pesos (puede ser negativo).
    available: float
    #: Siempre ``"ARS"``.
    currency: str

    @classmethod
    def retrieve(cls, *, options: RequestOptions | None = None) -> Balance:
        """Estilo global: ``rayacash.Balance.retrieve()``. Ver ``client.balance.retrieve()``."""
        from rayacash._balance_service import BalanceService
        from rayacash._global import default_requestor

        return BalanceService(default_requestor()).retrieve(options=options)

    @classmethod
    async def retrieve_async(cls, *, options: RequestOptions | None = None) -> Balance:
        from rayacash._balance_service import BalanceService
        from rayacash._global import default_requestor

        return await BalanceService(default_requestor()).retrieve_async(options=options)
