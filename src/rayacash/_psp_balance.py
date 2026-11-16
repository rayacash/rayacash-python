"""Los saldos de Raya PSP: el de un cliente (``psp.customer_balance``) y el tuyo con el de tus
clientes (``psp.balance``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import Literal

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._psp_service import PspBalanceService


def _service() -> PspBalanceService:
    from rayacash._global import default_requestor
    from rayacash._psp_service import PspBalanceService

    return PspBalanceService(default_requestor())


class PspCustomerBalance(RayaObject):
    """El saldo de un cliente de Raya PSP: lo devuelve
    ``client.psp.customers.retrieve_balance(customer_id)``.

    Para transferir en su nombre tienen que alcanzar su saldo y el tuyo: ``transferable`` ya lo
    tiene en cuenta. No tiene en cuenta el límite mensual del cliente: una transferencia a una
    cuenta fuera de Raya que lo supera responde ``422`` ``LIMIT_EXCEEDED``.
    """

    OBJECT_NAME = "psp.customer_balance"

    object: Literal["psp.customer_balance"]
    #: El ``id`` del cliente (``pspc_…``).
    customer: str
    #: Su saldo, en pesos: sube con lo que recibe y baja con lo que transferís en su nombre.
    available: float
    #: Lo que podés transferir ahora en su nombre, en pesos: lo que alcance de su saldo y del tuyo
    #: (tu saldo manda), y ``0`` si su ``status`` no es ``active``.
    transferable: float
    #: Siempre ``"ARS"``.
    currency: str


class PspBalance(RayaObject):
    """Tu saldo y el de tus clientes de Raya PSP: lo devuelve ``client.psp.balance.retrieve()``.

    Lo que reciben tus clientes se acredita en tu cuenta y suma a tu saldo; cada cliente lleva
    además el suyo (``PspCustomer.balance``).
    """

    OBJECT_NAME = "psp.balance"

    object: Literal["psp.balance"]
    #: Tu saldo disponible, en pesos: el mismo de ``client.balance.retrieve().available``. Puede
    #: ser negativo.
    available: float
    #: La suma de los saldos de tus clientes, en pesos (también la de los que tienen el CVU dado de
    #: baja).
    customers_balance: float
    #: Siempre ``"ARS"``.
    currency: str

    @classmethod
    def retrieve(cls, *, options: RequestOptions | None = None) -> PspBalance:
        """Estilo global: ``rayacash.PspBalance.retrieve()``. Ver
        ``client.psp.balance.retrieve()``."""
        return _service().retrieve(options=options)

    @classmethod
    async def retrieve_async(cls, *, options: RequestOptions | None = None) -> PspBalance:
        return await _service().retrieve_async(options=options)
