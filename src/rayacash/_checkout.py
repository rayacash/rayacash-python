"""Solo para leer los pickles de la 1.1.0: se borra en la 2.0.0. No lo importes.

En la 1.1.0, ``Checkout`` vivía en este módulo, así que un pickle de entonces guarda la clase como
``rayacash._checkout.Checkout`` (y sus ítems, como ``rayacash._checkout.Checkout.Item``). Acá
``Checkout`` es ``ConnectOrder``, la misma clase: ese pickle se lee como un ``ConnectOrder``, con
sus ``ConnectOrder.Item``, ``BankTransfer``, ``Payer`` y ``BackUrls``. Los pickles de la 1.2.0
guardan ``rayacash._connect_order.ConnectOrder``. En tu código, usá ``rayacash.ConnectOrder``.
"""

from __future__ import annotations

from rayacash._connect_order import ConnectOrder as Checkout
from rayacash._connect_order import ConnectOrderStatus as CheckoutStatus

__all__ = ["Checkout", "CheckoutStatus"]
