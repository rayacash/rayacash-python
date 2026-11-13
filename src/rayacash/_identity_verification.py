from __future__ import annotations

from collections.abc import Coroutine, Mapping
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    overload,
)

from typing_extensions import Literal, Protocol

from rayacash._identity_verification_files import IdentityVerificationFiles
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._identity_verification_service import IdentityVerificationService
    from rayacash._list_object import ListObject

IdentityVerificationType = Literal["document", "biometric"]
IdentityVerificationStatus = Literal[
    "pending", "in_progress", "processing", "verified", "declined", "expired", "canceled"
]
IdentityVerificationCheckStatus = Literal[
    "passed", "failed", "pending", "unavailable", "not_applicable"
]
IdentityVerificationDeclineCode = Literal[
    "face_mismatch",
    "registry_not_found",
    "registry_data_mismatch",
    "registry_unavailable",
    "attempts_exhausted",
]


def _service(verification: RayaObject | None = None) -> IdentityVerificationService:
    from rayacash._global import default_requestor
    from rayacash._identity_verification_service import IdentityVerificationService

    requestor = (
        verification._resolve_requestor() if verification is not None else default_requestor()
    )
    return IdentityVerificationService(requestor)


def _verification_id(verification: RayaObject) -> str:
    verification_id = verification.get("id")
    if not isinstance(verification_id, str) or not verification_id:
        raise ValueError("Esta IdentityVerification no tiene id: no se puede cancelar.")
    return verification_id


class _CancelById(Protocol):
    def __call__(
        self,
        verification_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> IdentityVerification: ...


class _CancelSelf(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> IdentityVerification: ...


class _CancelByIdAsync(Protocol):
    def __call__(
        self,
        verification_id: str,
        *,
        idempotency_key: str | None = ...,
        options: RequestOptions | None = ...,
    ) -> Coroutine[Any, Any, IdentityVerification]: ...


class _CancelSelfAsync(Protocol):
    def __call__(
        self, *, idempotency_key: str | None = ..., options: RequestOptions | None = ...
    ) -> Coroutine[Any, Any, IdentityVerification]: ...


class _CancelMethod:
    """``IdentityVerification.cancel(verification_id)`` desde la clase y ``verification.cancel()``
    desde una verificación."""

    @overload
    def __get__(self, verification: None, owner: type | None = None) -> _CancelById: ...

    @overload
    def __get__(
        self, verification: IdentityVerification, owner: type | None = None
    ) -> _CancelSelf: ...

    def __get__(
        self, verification: IdentityVerification | None, owner: type | None = None
    ) -> _CancelById | _CancelSelf:
        if verification is None:

            def cancel_by_id(
                verification_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> IdentityVerification:
                return _service().cancel(
                    verification_id, idempotency_key=idempotency_key, options=options
                )

            return cancel_by_id

        def cancel(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> IdentityVerification:
            return _service(verification).cancel(
                _verification_id(verification), idempotency_key=idempotency_key, options=options
            )

        return cancel


class _CancelAsyncMethod:
    @overload
    def __get__(self, verification: None, owner: type | None = None) -> _CancelByIdAsync: ...

    @overload
    def __get__(
        self, verification: IdentityVerification, owner: type | None = None
    ) -> _CancelSelfAsync: ...

    def __get__(
        self, verification: IdentityVerification | None, owner: type | None = None
    ) -> _CancelByIdAsync | _CancelSelfAsync:
        if verification is None:

            async def cancel_by_id(
                verification_id: str,
                *,
                idempotency_key: str | None = None,
                options: RequestOptions | None = None,
            ) -> IdentityVerification:
                return await _service().cancel_async(
                    verification_id, idempotency_key=idempotency_key, options=options
                )

            return cancel_by_id

        async def cancel(
            *, idempotency_key: str | None = None, options: RequestOptions | None = None
        ) -> IdentityVerification:
            return await _service(verification).cancel_async(
                _verification_id(verification), idempotency_key=idempotency_key, options=options
            )

        return cancel


class IdentityVerification(RayaObject):
    """Una verificación de Identidad: la persona le saca una foto a su DNI, hace una prueba de vida
    y validamos sus datos y su cara contra el Registro Nacional de las Personas (RENAPER).

    ``document`` es la completa: DNI (frente y dorso), prueba de vida y validación contra el
    registro. ``biometric`` es solo una prueba de vida, comparada con la de una ``document``
    anterior de la misma persona (``reference``). Dala por buena solo cuando ``status`` es
    ``verified``.

    Es el mismo objeto que llega en los webhooks ``identity.verification.*``, ahí siempre con
    ``person`` en ``None``: pedí los datos con ``client.identity.verifications.retrieve(id)``.
    """

    OBJECT_NAME = "identity.verification"

    class DeclineReason(RayaObject):
        """Por qué se rechazó. Decidí con ``code``, no con ``message``."""

        #: ``face_mismatch``, ``registry_not_found``, ``registry_data_mismatch``,
        #: ``registry_unavailable`` o ``attempts_exhausted`` (pueden sumarse valores).
        code: IdentityVerificationDeclineCode
        #: El motivo en palabras, en castellano: puede cambiar.
        message: str

    class DocumentCheck(RayaObject):
        """La lectura del DNI: frente y dorso."""

        status: IdentityVerificationCheckStatus

    class LivenessCheck(RayaObject):
        """La prueba de vida: que haya una persona real frente a la cámara."""

        status: IdentityVerificationCheckStatus
        #: Qué tan segura es la prueba, de 0 a 100. ``None`` hasta que el control termina.
        confidence: float | None

    class FaceMatchCheck(RayaObject):
        """La selfie contra la foto del DNI (``document``) o contra la selfie de la verificación de
        ``reference`` (``biometric``)."""

        status: IdentityVerificationCheckStatus
        #: Parecido entre las dos caras, de 0 a 100. ``None`` hasta que el control termina.
        similarity: float | None

    class RegistryCheck(RayaObject):
        """La validación contra el registro. En una ``biometric``, ``not_applicable``."""

        #: ``unavailable``: el registro no respondió en 24 horas; la verificación queda
        #: ``declined`` con ``registry_unavailable`` y no se cobra.
        status: IdentityVerificationCheckStatus
        #: Si los datos leídos del DNI coinciden con los del registro.
        data_match: bool | None
        #: La cara contra la del registro: ``hit`` (es la misma persona), ``accepted`` (el
        #: parecido alcanza el mínimo que aceptamos) o ``failed`` (pueden sumarse valores).
        face_match: Literal["hit", "accepted", "failed"] | None

    class Checks(RayaObject):
        """Cada control con su resultado: ``passed``, ``failed``, ``pending`` (todavía no se hizo),
        ``unavailable`` o ``not_applicable`` (este tipo de verificación no lo lleva)."""

        document: IdentityVerification.DocumentCheck
        liveness: IdentityVerification.LivenessCheck
        face_match: IdentityVerification.FaceMatchCheck
        registry: IdentityVerification.RegistryCheck

    class Address(RayaObject):
        """El domicilio que figura en el registro. Cualquier campo puede ser ``None``."""

        street: str | None
        #: La altura.
        number: str | None
        floor: str | None
        apartment: str | None
        #: La localidad.
        city: str | None
        #: El partido o departamento.
        municipality: str | None
        province: str | None
        postal_code: str | None
        country: str | None

    class IdentityDocument(RayaObject):
        """El ejemplar del DNI. Fechas ``YYYY-MM-DD``; cualquier campo puede ser ``None``.

        El ejemplar (``A``, ``B``…) se lee con ``document["copy"]``: como todo ``RayaObject`` es
        un ``dict``, ``document.copy`` es el método ``copy()`` de ``dict``.
        """

        # copy: str | None -> se lee con document["copy"]: el atributo es dict.copy(). Anotarlo
        # acá le mentiría al type checker (y pisa el método para mypy y pyright).
        #: Fecha de emisión.
        issue_date: str | None
        #: Fecha de vencimiento.
        expiry_date: str | None

    class Person(RayaObject):
        """Los datos de la persona según el registro. Cualquier campo puede ser ``None``.

        Son datos personales: no los loguees y guardá solo lo que necesitás.
        """

        first_name: str | None
        last_name: str | None
        #: Hoy, siempre ``"DNI"``.
        document_type: str | None
        #: El número de documento, sin puntos.
        document_number: str | None
        #: ``F``, ``M`` o ``X``.
        sex: str | None
        #: ``YYYY-MM-DD``.
        birth_date: str | None
        nationality: str | None
        #: 11 dígitos, sin guiones.
        cuil: str | None
        address: IdentityVerification.Address
        document: IdentityVerification.IdentityDocument

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "decline_reason": DeclineReason,
        "checks": Checks,
        "person": Person,
    }
    _plain_fields: ClassVar[frozenset[str]] = frozenset({"metadata"})

    #: ``idv_`` y 24 letras o números.
    id: str
    object: Literal["identity.verification"]
    #: ``document`` o ``biometric``.
    type: IdentityVerificationType
    #: ``pending`` (nadie empezó), ``in_progress``, ``processing`` (terminó la captura),
    #: ``verified``, ``declined``, ``expired`` o ``canceled`` (pueden sumarse valores).
    status: IdentityVerificationStatus
    #: La página donde la persona hace la verificación: mandásela o abrila con Identity.js. Quien
    #: tenga el link puede hacerla: compartilo solo con esa persona.
    url: str
    #: Tu identificador (por ejemplo, el id de tu cliente).
    external_reference: str | None
    #: Tus pares clave-valor (un dict común). ``{}`` si no mandaste ninguno.
    metadata: dict[str, str]
    #: A dónde puede volver la persona desde la pantalla final.
    return_url: str | None
    #: En una ``biometric``, el ``id`` de la verificación ``document`` contra la que se compara.
    reference: str | None
    #: Por qué se rechazó; ``None`` si no está ``declined``.
    decline_reason: DeclineReason | None
    checks: Checks
    #: Los datos de la persona, solo cuando está ``verified``. En los eventos viene siempre en
    #: ``None``: pedila con ``client.identity.verifications.retrieve(id)``.
    person: Person | None
    #: Lo que se cobra por esta verificación, en pesos: queda fijo cuando pasa a ``verified``
    #: (``None`` en cualquier otro estado).
    amount: float | None
    #: Siempre ``"ARS"``.
    currency: str
    #: Fecha ISO 8601 en UTC, como ``"2026-10-24T18:00:00Z"``.
    created_at: str
    #: Cuándo la persona tocó «Empezar» por primera vez.
    started_at: str | None
    #: Cuándo terminó la captura.
    submitted_at: str | None
    #: Cuándo llegó a un estado final.
    completed_at: str | None
    #: Hasta cuándo la persona puede completarla.
    expires_at: str

    #: Cancela la verificación (solo ``pending`` o ``in_progress``).
    #: ``IdentityVerification.cancel(verification_id)`` o ``verification.cancel()``.
    cancel = _CancelMethod()
    cancel_async = _CancelAsyncMethod()

    # --- Estilo global (rayacash.IdentityVerification.*); ver IdentityVerificationService. ---

    @classmethod
    def create(
        cls,
        *,
        type: IdentityVerificationType,  # noqa: A002 - el nombre del parámetro en la API
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        return_url: str | None = None,
        expires_in: int | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> IdentityVerification:
        """Crea una verificación con tu clave secreta en ``rayacash.api_key`` (o en
        ``options["api_key"]``)."""
        return _service().create(
            type=type,
            external_reference=external_reference,
            metadata=metadata,
            return_url=return_url,
            expires_in=expires_in,
            reference=reference,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    async def create_async(
        cls,
        *,
        type: IdentityVerificationType,  # noqa: A002 - el nombre del parámetro en la API
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        return_url: str | None = None,
        expires_in: int | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> IdentityVerification:
        return await _service().create_async(
            type=type,
            external_reference=external_reference,
            metadata=metadata,
            return_url=return_url,
            expires_in=expires_in,
            reference=reference,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(
        cls, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerification:
        return _service().retrieve(verification_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerification:
        return await _service().retrieve_async(verification_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        status: IdentityVerificationStatus | None = None,
        type: IdentityVerificationType | None = None,  # noqa: A002 - el filtro de la API
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[IdentityVerification]:
        return _service().list(
            status=status,
            type=type,
            external_reference=external_reference,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )

    @classmethod
    async def list_async(
        cls,
        *,
        status: IdentityVerificationStatus | None = None,
        type: IdentityVerificationType | None = None,  # noqa: A002 - el filtro de la API
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[IdentityVerification]:
        return await _service().list_async(
            status=status,
            type=type,
            external_reference=external_reference,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )

    @classmethod
    def files(
        cls, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerificationFiles:
        """Las imágenes de una verificación: ``rayacash.IdentityVerification.files(id)``."""
        return _service().files(verification_id, options=options)

    @classmethod
    async def files_async(
        cls, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerificationFiles:
        return await _service().files_async(verification_id, options=options)


# Los sub-objetos de checks y de person tienen clases hermanas, no hijas
# (IdentityVerification.DocumentCheck, como en Node.js y PHP): el cuerpo de una clase anidada no
# ve a sus hermanas, así que se enlazan acá, con IdentityVerification ya armada.
IdentityVerification.Checks._inner_class_types = {
    "document": IdentityVerification.DocumentCheck,
    "liveness": IdentityVerification.LivenessCheck,
    "face_match": IdentityVerification.FaceMatchCheck,
    "registry": IdentityVerification.RegistryCheck,
}
IdentityVerification.Person._inner_class_types = {
    "address": IdentityVerification.Address,
    "document": IdentityVerification.IdentityDocument,
}
