"""Los nombres de la 1.1.0 que la 1.2.0 cambió por los de Raya Connect.

Siguen andando hasta la 2.0.0 como alias deprecados: son el mismo objeto que el nombre nuevo (o,
para ``checkout_id=``, el mismo parámetro que ``order_id=``) y cada uso avisa con un
``DeprecationWarning`` que apunta a la línea de tu código. Los type checkers los ven marcados con
``@deprecated`` (PEP 702). En la 2.0.0 se borran este módulo, ``rayacash._checkout`` y los alias.

- ``rayacash.Checkout`` y ``rayacash.CheckoutStatus``: ``__getattr__`` de ``rayacash``.
- ``client.checkout``: una property de ``RayaClient`` que devuelve ``client.connect``. Como el
  atributo común que era, se puede asignar y borrar (``mock.patch.object``, ``monkeypatch``).
- ``checkout_id=`` en ``retrieve`` y ``refund`` (y sus ``*_async``) de ``client.connect.orders``
  y de ``rayacash.ConnectOrder``: ``accepts_checkout_id`` y ``accepts_checkout_id_async``.
- ``rayacash._checkout``: el módulo de ``Checkout`` en la 1.1.0, solo para que sus pickles se
  sigan leyendo. No avisa: es privado y solo lo importa ``pickle``.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Coroutine
from typing import Any, Callable, TypeVar

_R = TypeVar("_R")


def deprecation_message(old: str, new: str) -> str:
    """El texto del aviso. Los ``@deprecated("…")`` de los type checkers repiten este mismo texto
    (tiene que ser un literal) y un test chequea que coincidan."""
    return f"{old} está deprecado desde la 1.2.0 y se va en la 2.0.0: usá {new}."


def warn_deprecated(old: str, new: str, *, stacklevel: int = 2) -> None:
    """Emite el ``DeprecationWarning``. ``stacklevel`` cuenta desde quien llama a esta función,
    como en ``warnings.warn``: con 2, apunta a quien llamó a esa función."""
    warnings.warn(deprecation_message(old, new), DeprecationWarning, stacklevel=stacklevel + 1)


def _rename_checkout_id(kwargs: dict[str, Any]) -> None:
    if "checkout_id" not in kwargs:
        return
    if "order_id" in kwargs:
        raise TypeError("Pasá order_id o checkout_id (deprecado), no los dos.")
    # 3: _rename_checkout_id → el wrapper → tu código.
    warn_deprecated("checkout_id", "order_id", stacklevel=3)
    kwargs["order_id"] = kwargs.pop("checkout_id")


def accepts_checkout_id(func: Callable[..., _R]) -> Callable[..., _R]:
    """Acepta ``checkout_id=``, el nombre de la 1.1.0, como ``order_id=``.

    El tipado lo dan los ``@overload`` del método (uno con ``@deprecated``); la firma visible
    (``help()``, ``inspect.signature``) sigue siendo la de ``func``.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> _R:
        _rename_checkout_id(kwargs)
        return func(*args, **kwargs)

    return wrapper


def accepts_checkout_id_async(
    func: Callable[..., Coroutine[Any, Any, _R]],
) -> Callable[..., Coroutine[Any, Any, _R]]:
    """Como ``accepts_checkout_id``, para los ``*_async``: el wrapper también es una corrutina."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> _R:
        _rename_checkout_id(kwargs)
        return await func(*args, **kwargs)

    return wrapper
