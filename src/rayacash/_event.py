from __future__ import annotations

from typing import ClassVar

from typing_extensions import Literal

from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer

#: Los tipos de evento que existen hoy. Pueden sumarse otros: tu código tiene que ignorarlos.
EventType = Literal[
    "transfer.received",
    "transfer.sent",
    "transfer.failed",
    "payment.created",
    "payment.succeeded",
    "payment.failed",
    "payment.refunded",
    "webhook.test",
]


class Event(RayaObject):
    """Un evento de webhook. Armalo con ``rayacash.Webhook.construct_event(...)``.

    ``event.data.object`` es el ``Transfer`` o el ``Payment`` tal como estaba cuando ocurrió el
    evento. ``webhook.test`` (el botón «Enviar evento de prueba») trae ``{"object": "test", …}``:
    respondé 2xx e ignoralo.
    """

    OBJECT_NAME = "event"

    class Data(RayaObject):
        object: Transfer | Payment | RayaObject

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {"data": Data}

    #: ``evt_…``: el mismo valor que el header ``Raya-Event-Id``. Procesá cada uno una vez.
    id: str
    object: Literal["event"]
    type: EventType
    #: Versión del formato del evento, por ahora ``"2026-10-23"``.
    api_version: str
    #: Cuándo ocurrió (ISO 8601 en UTC).
    created_at: str
    data: Data
