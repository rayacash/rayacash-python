from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Literal

from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._user_service import UserService

UserType = Literal["personal", "business"]


def _service() -> UserService:
    from rayacash._global import default_requestor
    from rayacash._user_service import UserService

    return UserService(default_requestor())


class User(RayaObject):
    """Una cuenta de Raya que conectó tu aplicación, con los datos que verificó Raya.

    Solo podés leerla con su propio access_token: cualquier otro id da ``USER_NOT_FOUND``. Nunca
    viene la foto del documento ni el número de trámite. Los campos sin dato vienen en ``None``.
    """

    OBJECT_NAME = "user"

    class Identification(RayaObject):
        """El documento que identifica a la cuenta."""

        #: ``DNI`` en una cuenta personal; ``CUIT`` en una empresa. El CUIL de una persona va
        #: en ``tax_id``.
        type: Literal["DNI", "CUIT"]
        #: Solo dígitos.
        number: str

    class Address(RayaObject):
        """El domicilio que figura en RENAPER. Cada campo puede ser ``None``."""

        street: str | None
        number: str | None
        floor: str | None
        apartment: str | None
        city: str | None
        province: str | None
        postal_code: str | None
        country: str | None

    class Business(RayaObject):
        """Los datos de la empresa (solo si ``type`` es ``business``)."""

        class Representative(RayaObject):
            """Quien representa a la empresa ante Raya."""

            first_name: str | None
            last_name: str | None
            #: CUIL del representante: 11 dígitos, sin guiones.
            tax_id: str | None

        _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
            "representative": Representative
        }

        #: La razón social.
        legal_name: str | None
        #: CUIT de la empresa: 11 dígitos, sin guiones.
        tax_id: str | None
        #: El tipo societario (S.A., S.R.L.…).
        company_type: str | None
        representative: Representative | None

    class Merchant(RayaObject):
        """El negocio de la cuenta, como lo ve quien paga."""

        #: El nombre visible en la página de pago.
        name: str
        #: La imagen del negocio, o ``None``.
        image: str | None

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "identification": Identification,
        "address": Address,
        "business": Business,
        "merchant": Merchant,
    }

    #: El ``user_id`` que vino con el access_token.
    id: str
    object: Literal["user"]
    #: ``personal`` o ``business``.
    type: UserType
    email: str
    #: De la persona titular; en una empresa, ``first_name`` y ``full_name`` traen la razón
    #: social y ``last_name`` es ``None``. ``None`` donde no hay dato.
    first_name: str | None
    last_name: str | None
    full_name: str | None
    #: El DNI (cuenta personal) o el CUIT (empresa). ``None`` si todavía no lo verificamos.
    identification: Identification | None
    #: CUIL (personal) o CUIT (empresa): 11 dígitos, sin guiones.
    tax_id: str | None
    phone: str | None
    #: ``YYYY-MM-DD``.
    date_of_birth: str | None
    sex: Literal["M", "F", "X"] | None
    nationality: str | None
    address: Address | None
    #: Si Raya verificó la identidad de la cuenta.
    identity_verified: bool
    #: Cuándo la verificó (ISO 8601 en UTC).
    verified_at: str | None
    business: Business | None
    #: ``None`` si la cuenta todavía no configuró su negocio (no se le pueden crear checkouts).
    merchant: Merchant | None
    created_at: str

    # --- Estilo global (rayacash.User.*); ver UserService para el detalle. ---

    @classmethod
    def retrieve(cls, user_id: str, *, options: RequestOptions | None = None) -> User:
        """Estilo global: ``rayacash.User.retrieve(user_id)``. Ver ``client.users.retrieve()``."""
        return _service().retrieve(user_id, options=options)

    @classmethod
    async def retrieve_async(cls, user_id: str, *, options: RequestOptions | None = None) -> User:
        return await _service().retrieve_async(user_id, options=options)
