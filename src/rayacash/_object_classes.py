"""Qué clase le toca a cada valor de ``object``. Lo que no está acá queda como RayaObject."""

from __future__ import annotations

from rayacash._balance import Balance
from rayacash._connect_order import ConnectOrder
from rayacash._event import Event
from rayacash._list_object import ListObject
from rayacash._oauth import OAuthToken
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer
from rayacash._user import User

# Las claves son el valor entero de ``object``, con el punto incluido: "connect.order" es una
# sola clave (nada parte el nombre en "connect" y "order"). "checkout" es su nombre en la 1.1.0:
# los eventos de antes del cambio quedan guardados con ese body y se pueden reenviar.
OBJECT_CLASSES: dict[str, type[RayaObject]] = {
    "balance": Balance,
    "checkout": ConnectOrder,  # legacy (1.1.0)
    "connect.order": ConnectOrder,
    "event": Event,
    "list": ListObject,
    "oauth_token": OAuthToken,
    "payment": Payment,
    "transfer": Transfer,
    "user": User,
}
