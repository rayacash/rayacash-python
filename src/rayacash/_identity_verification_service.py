from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rayacash._encoding import encode_query, path_id
from rayacash._identity_verification import (
    IdentityVerification,
    IdentityVerificationStatus,
    IdentityVerificationType,
)
from rayacash._identity_verification_files import IdentityVerificationFiles
from rayacash._list_object import ListObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor

_PATH = "/v1/identity/verifications"


def _create_body(
    verification_type: str,
    external_reference: str | None,
    metadata: Mapping[str, str] | None,
    return_url: str | None,
    expires_in: int | None,
    reference: str | None,
) -> dict[str, Any]:
    """El body en el orden del contrato (``identity/api_params.py`` de la API).

    Los rangos y los formatos los valida la API, con ``data.field``: acá, solo las formas que
    nunca pueden andar.
    """
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError('metadata tiene que ser un dict de str a str, como {"plan": "pro"}.')
    if expires_in is not None and (isinstance(expires_in, bool) or not isinstance(expires_in, int)):
        raise TypeError(
            "expires_in tiene que ser un int: los segundos que tiene la persona para completar "
            "la verificación (de 3600 a 2592000)."
        )
    return {
        "type": verification_type,
        "external_reference": external_reference,
        "metadata": metadata,
        "return_url": return_url,
        "expires_in": expires_in,
        "reference": reference,
    }


def _verification_path(verification_id: str, action: str = "") -> str:
    return f"{_PATH}/{path_id('verification_id', verification_id)}{action}"


def _list_query(
    status: str | None,
    verification_type: str | None,
    external_reference: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "status": status,
            "type": verification_type,
            "external_reference": external_reference,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


class IdentityVerificationService:
    """``client.identity.verifications``: verificar la identidad de una persona y leer el resultado.

    Usá un ``RayaClient`` con tu clave secreta (``raya_sk_live_…``), siempre desde tu servidor. En
    el navegador va Identity.js (``npm install rayacash-identity``), que no usa ninguna clave:
    solo el ``id`` de la verificación.
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
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
        """Crea una verificación ``pending`` (``POST /v1/identity/verifications``).

        Mandale ``url`` a la persona o abrila adentro de tu sitio con Identity.js; te avisamos el
        resultado con los webhooks ``identity.verification.*``. Crearla no tiene costo: se cobra
        solo si termina ``verified``.

        :param type: ``document`` (DNI, prueba de vida y registro) o ``biometric`` (solo una
            prueba de vida, contra la de una ``document`` anterior de la misma persona).
        :param external_reference: Tu identificador, como el id de tu cliente: hasta 128
            caracteres en una línea. No pongas datos personales: al filtrar la lista viaja en la
            URL.
        :param metadata: Hasta 20 pares clave-valor de texto.
        :param return_url: URL ``https://`` a la que puede volver la persona desde la pantalla
            final. No pongas datos personales en ella.
        :param expires_in: Segundos que tiene la persona para completarla, de 3600 (1 hora) a
            2592000 (30 días). Por defecto, 7 días.
        :param reference: Solo con ``type="biometric"``, donde es obligatorio: el ``id`` de una
            verificación ``document`` de tu cuenta en estado ``verified``, con
            ``checks.registry.face_match`` en ``hit``.
        :param idempotency_key: Recomendada: guardala con tu cliente y reusala si reintentás. Si
            no la pasás, generamos una que protege los reintentos de esta llamada.
        """
        return cast(
            IdentityVerification,
            self._requestor.request(
                "POST",
                _PATH,
                body=_create_body(
                    type, external_reference, metadata, return_url, expires_in, reference
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=IdentityVerification,
            ),
        )

    async def create_async(
        self,
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
        """Como ``create()``, para asyncio."""
        return cast(
            IdentityVerification,
            await self._requestor.request_async(
                "POST",
                _PATH,
                body=_create_body(
                    type, external_reference, metadata, return_url, expires_in, reference
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=IdentityVerification,
            ),
        )

    def retrieve(
        self, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerification:
        """Una verificación de tu cuenta, con ``person`` si está ``verified``
        (``GET /v1/identity/verifications/:id``)."""
        return cast(
            IdentityVerification,
            self._requestor.request(
                "GET",
                _verification_path(verification_id),
                options=options,
                expected=IdentityVerification,
            ),
        )

    async def retrieve_async(
        self, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerification:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            IdentityVerification,
            await self._requestor.request_async(
                "GET",
                _verification_path(verification_id),
                options=options,
                expected=IdentityVerification,
            ),
        )

    def list(
        self,
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
        """Tus verificaciones, de la más nueva a la más vieja (``GET /v1/identity/verifications``):
        las de la API y las del dashboard, cada una completa.

        Devuelve una página. Para recorrer todas: ``.auto_paging_iter()``.

        :param status: ``pending``, ``in_progress``, ``processing``, ``verified``, ``declined``,
            ``expired`` o ``canceled``.
        :param type: ``document`` o ``biometric``.
        :param external_reference: Coincidencia exacta.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _list_query(
            status, type, external_reference, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[IdentityVerification]",
            self._requestor.request_list(_PATH, query=query, options=options),
        )

    async def list_async(
        self,
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
        """Como ``list()``, para asyncio."""
        query = _list_query(
            status, type, external_reference, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[IdentityVerification]",
            await self._requestor.request_list_async(_PATH, query=query, options=options),
        )

    def cancel(
        self,
        verification_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> IdentityVerification:
        """Cancela una verificación que la persona todavía no terminó (``POST …/cancel``).

        Su link deja de funcionar y no se cobra. Solo ``pending`` o ``in_progress``: si no,
        ``ConflictError`` con ``code == "VERIFICATION_NOT_CANCELABLE"`` y el estado en
        ``error.data["status"]``. Cancelar una que ya está ``canceled`` la devuelve igual. Te
        avisamos con ``identity.verification.canceled``.
        """
        return cast(
            IdentityVerification,
            self._requestor.request(
                "POST",
                _verification_path(verification_id, "/cancel"),
                idempotency_key=idempotency_key,
                options=options,
                expected=IdentityVerification,
            ),
        )

    async def cancel_async(
        self,
        verification_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> IdentityVerification:
        """Como ``cancel()``, para asyncio."""
        return cast(
            IdentityVerification,
            await self._requestor.request_async(
                "POST",
                _verification_path(verification_id, "/cancel"),
                idempotency_key=idempotency_key,
                options=options,
                expected=IdentityVerification,
            ),
        )

    def files(
        self, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerificationFiles:
        """Las imágenes de una verificación, con URLs que vencen a los 5 minutos
        (``GET /v1/identity/verifications/:id/files``)."""
        return cast(
            IdentityVerificationFiles,
            self._requestor.request(
                "GET",
                _verification_path(verification_id, "/files"),
                options=options,
                expected=IdentityVerificationFiles,
            ),
        )

    async def files_async(
        self, verification_id: str, *, options: RequestOptions | None = None
    ) -> IdentityVerificationFiles:
        """Como ``files()``, para asyncio."""
        return cast(
            IdentityVerificationFiles,
            await self._requestor.request_async(
                "GET",
                _verification_path(verification_id, "/files"),
                options=options,
                expected=IdentityVerificationFiles,
            ),
        )


class IdentityService:
    """``client.identity``: Identidad, la verificación de identidad de tus clientes.

    ``client.identity.verifications`` crea las verificaciones y lee su resultado, con tu clave
    secreta. Referencia: https://raya.cash/api/identity
    """

    verifications: IdentityVerificationService

    def __init__(self, requestor: APIRequestor) -> None:
        self.verifications = IdentityVerificationService(requestor)
