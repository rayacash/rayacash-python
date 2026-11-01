"""Qué clase le toca a cada valor de ``object``. Lo que no está acá queda como RayaObject."""

from __future__ import annotations

from rayacash._balance import Balance
from rayacash._event import Event
from rayacash._list_object import ListObject
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer

OBJECT_CLASSES: dict[str, type[RayaObject]] = {
    "balance": Balance,
    "event": Event,
    "list": ListObject,
    "payment": Payment,
    "transfer": Transfer,
}
