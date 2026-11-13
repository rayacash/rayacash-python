from __future__ import annotations

from typing import ClassVar

from typing_extensions import Literal

from rayacash._raya_object import RayaObject


class IdentityVerificationFiles(RayaObject):
    """Las imágenes de una verificación de Identidad: el frente y el dorso del DNI y la selfie de la
    prueba de vida, cada una con una URL firmada que vence a los 5 minutos.

    Lo devuelve ``client.identity.verifications.files(verification_id)``, con las imágenes
    guardadas hasta ese momento, en cualquier estado. Bajá cada una enseguida, desde tu servidor y
    con tu propio cliente HTTP, y no guardes las URLs: si vencieron, pedilas de nuevo. La que esa
    verificación no tiene viene en ``None`` (una ``biometric`` solo tiene ``selfie``). Son datos
    personales: guardá solo lo que necesitás.
    """

    OBJECT_NAME = "identity.verification_files"

    class File(RayaObject):
        """Una imagen de la verificación."""

        #: URL firmada de la imagen (JPEG). Sirve 5 minutos: no la guardes.
        url: str
        #: Hasta cuándo sirve la URL (ISO 8601 en UTC).
        expires_at: str

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "front": File,
        "back": File,
        "selfie": File,
    }

    object: Literal["identity.verification_files"]
    #: El frente del DNI.
    front: File | None
    #: El dorso del DNI.
    back: File | None
    #: La selfie de la prueba de vida.
    selfie: File | None
