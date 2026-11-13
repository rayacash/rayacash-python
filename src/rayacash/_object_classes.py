"""Qué clase le toca a cada valor de ``object``. Lo que no está acá queda como RayaObject."""

from __future__ import annotations

from rayacash._balance import Balance
from rayacash._connect_order import ConnectOrder
from rayacash._connect_payout import ConnectPayout
from rayacash._event import Event
from rayacash._identity_verification import IdentityVerification
from rayacash._identity_verification_files import IdentityVerificationFiles
from rayacash._list_object import ListObject
from rayacash._oauth import OAuthToken
from rayacash._payment import Payment
from rayacash._raya_object import RayaObject
from rayacash._transfer import Transfer
from rayacash._user import User

# Las claves son el valor entero de ``object``, con el punto incluido: "connect.order",
# "connect.payout", "identity.verification" e "identity.verification_files" son una sola clave
# cada una (nada parte el nombre en "connect" o "identity" y el resto).
# "checkout" es el nombre de "connect.order" en la 1.1.0:
# los eventos de antes del cambio quedan guardados con ese body y se pueden reenviar.
OBJECT_CLASSES: dict[str, type[RayaObject]] = {
    "balance": Balance,
    "checkout": ConnectOrder,  # legacy (1.1.0)
    "connect.order": ConnectOrder,
    "connect.payout": ConnectPayout,
    "event": Event,
    "identity.verification": IdentityVerification,
    "identity.verification_files": IdentityVerificationFiles,
    "list": ListObject,
    "oauth_token": OAuthToken,
    "payment": Payment,
    "transfer": Transfer,
    "user": User,
}
