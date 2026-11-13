from __future__ import annotations

from typing import ClassVar

from typing_extensions import Literal

from rayacash._connect_order import ConnectOrder
from rayacash._identity_verification import IdentityVerification
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer

#: Los tipos de evento que existen hoy. Pueden sumarse otros: tu código tiene que ignorarlos.
#: Los ``connect.order.*`` (Raya Connect) le llegan al dueño de la app; la cuenta conectada
#: recibe sus ``payment.*``. Los ``identity.verification.*`` (Identidad) avisan cuando una
#: verificación llega a un estado final. Los ``checkout.*`` del final son legacy, sus nombres en
#: la 1.1.0: la API ya no los emite (solo vuelven si reenviás desde el dashboard un evento de
#: antes del cambio) y quedan acá para que el código escrito para la 1.1.0 siga tipando.
#: Compará ``event.type`` con los ``connect.order.*``.
EventType = Literal[
    "transfer.received",
    "transfer.sent",
    "transfer.failed",
    "payment.created",
    "payment.succeeded",
    "payment.failed",
    "payment.refunded",
    "connect.order.created",
    "connect.order.succeeded",
    "connect.order.failed",
    "connect.order.refunded",
    "identity.verification.verified",
    "identity.verification.declined",
    "identity.verification.expired",
    "identity.verification.canceled",
    "webhook.test",
    # Legacy (1.1.0): la API ya no los emite.
    "checkout.created",
    "checkout.succeeded",
    "checkout.failed",
    "checkout.refunded",
]


class Event(RayaObject):
    """Un evento de webhook. Armalo con ``rayacash.Webhook.construct_event(...)``.

    ``event.data.object`` es el ``Transfer``, el ``Payment``, el ``ConnectOrder`` o la
    ``IdentityVerification`` (siempre con ``person`` en ``None``) tal como estaba cuando ocurrió
    el evento. ``webhook.test`` (el botón «Enviar evento de prueba») trae
    ``{"object": "test", …}``: respondé 2xx e ignoralo.

    ``livemode`` es ``False`` en los eventos de un sandbox y ``True`` en los de tu cuenta real.
    """

    OBJECT_NAME = "event"

    class Data(RayaObject):
        object: Transfer | Payment | ConnectOrder | IdentityVerification | RayaObject

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {"data": Data}

    #: ``evt_…``: el mismo valor que el header ``Raya-Event-Id``. Procesá cada uno una vez.
    id: str
    object: Literal["event"]
    type: EventType
    #: Versión del formato del evento, por ahora ``"2026-10-23"``.
    api_version: str
    #: Cuándo ocurrió (ISO 8601 en UTC).
    created_at: str
    #: ``True`` en tu cuenta real y ``False`` en un sandbox. Un evento creado antes de que la API
    #: sumara este campo (un reintento o un reenvío desde el dashboard) no lo trae, y de antemano
    #: no sabés cuál es así: leelo siempre con ``event.get("livemode", True)`` (``event.livemode``
    #: levanta ``AttributeError`` si falta).
    livemode: bool
    data: Data
