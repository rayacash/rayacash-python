"""Qué clase le toca a cada valor de ``object``. Lo que no está acá queda como RayaObject."""

from __future__ import annotations

from rayacash._balance import Balance
from rayacash._checkout import Checkout
from rayacash._event import Event
from rayacash._list_object import ListObject
from rayacash._oauth import OAuthToken
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer
from rayacash._user import User

OBJECT_CLASSES: dict[str, type[RayaObject]] = {
    "balance": Balance,
    "checkout": Checkout,
    "event": Event,
    "list": ListObject,
    "oauth_token": OAuthToken,
    "payment": Payment,
    "transfer": Transfer,
    "user": User,
}
