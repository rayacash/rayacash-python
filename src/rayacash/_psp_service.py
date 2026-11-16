"""``client.psp``: Raya PSP, cuentas con CVU a nombre de los clientes de tu empresa.

``PspService`` solo cuelga los tres servicios: ``customers`` (los clientes y sus acciones),
``transfers`` (lo que reciben y lo que transferís en su nombre) y ``balance`` (tu saldo y el de tus
clientes). Van con tu clave secreta. Los parámetros viajan en el orden de la API
(``pspexternal/api_params.py``) y solo los que vinieron: los ``None`` se omiten.
``customers.create`` tiene tres formas, una por ``@overload``: con Identidad (solo
``identity_verification``), con las fotos (una persona humana) o una persona jurídica.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast, overload

from typing_extensions import Literal

from rayacash._encoding import (
    Amount,
    canonical_amount,
    encode_query,
    path_id,
    validate_idempotency_key,
)
from rayacash._list_object import ListObject
from rayacash._psp_balance import PspBalance, PspCustomerBalance
from rayacash._psp_customer import (
    PspCustomer,
    PspCustomerAction,
    PspCustomerPersonType,
    PspCustomerStatus,
)
from rayacash._psp_transfer import PspTransfer, PspTransferDirection, PspTransferStatus
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor

_CUSTOMERS = "/v1/psp/customers"
_TRANSFERS = "/v1/psp/transfers"
_BALANCE = "/v1/psp/balance"


def _customer_path(customer_id: str, suffix: str = "") -> str:
    return f"{_CUSTOMERS}/{path_id('customer_id', customer_id)}{suffix}"


def _transfer_path(transfer_id: str) -> str:
    return f"{_TRANSFERS}/{path_id('transfer_id', transfer_id)}"


#: La pista de los ``TypeError`` de ``tax_id`` y ``name``: con Identidad no hacen falta.
_IDENTITY_HINT = " Si tu cliente se verificó con Raya Identity, mandá solo identity_verification."


def _create_customer_body(
    identity_verification: str | None,
    tax_id: str | None,
    name: str | None,
    person_type: str | None,
    document_front_url: str | None,
    document_back_url: str | None,
    selfie_url: str | None,
    external_reference: str | None,
    metadata: Mapping[str, str] | None,
) -> dict[str, Any]:
    """El body en el orden de ``CREATE_FIELDS`` de la API, validado en ese mismo orden.

    Acá, solo las formas que nunca pueden andar: ``identity_verification``, si viene, un ``str``;
    sin ella, ``tax_id`` y ``name`` obligatorios y ``str``. El resto (el CUIL, la coherencia entre
    ``person_type``, ``identity_verification`` y las fotos, las URLs) lo responde la API con
    ``data.field``.
    """
    if identity_verification is not None:
        if not isinstance(identity_verification, str):
            raise TypeError(
                "identity_verification tiene que ser un string con el id de una verificación de "
                f"Identidad (idv_…), no {type(identity_verification).__name__}."
            )
    else:
        if not isinstance(tax_id, str):
            raise TypeError(
                "tax_id tiene que ser un str: el CUIL o CUIT de tu cliente, 11 dígitos sin guiones."
                + _IDENTITY_HINT
            )
        if not isinstance(name, str):
            raise TypeError(
                "name tiene que ser un str: el nombre y apellido de tu cliente, o su razón social."
                + _IDENTITY_HINT
            )
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError('metadata tiene que ser un dict de str a str, como {"plan": "pro"}.')
    return {
        "identity_verification": identity_verification,
        "tax_id": tax_id,
        "name": name,
        "person_type": person_type,
        "document_front_url": document_front_url,
        "document_back_url": document_back_url,
        "selfie_url": selfie_url,
        "external_reference": external_reference,
        "metadata": metadata,
    }


def _customer_list_query(
    status: str | None,
    external_reference: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "status": status,
            "external_reference": external_reference,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


def _create_transfer_body(customer: str, amount: Amount, destination: str) -> dict[str, Any]:
    """El body en el orden de la API (``customer``, ``amount``, ``destination``), validado en ese
    mismo orden."""
    if not isinstance(customer, str):
        raise TypeError("customer tiene que ser un str: el id del cliente (pspc_…).")
    exact_amount = canonical_amount(amount)
    if not isinstance(destination, str):
        raise TypeError(
            "destination tiene que ser un str (CBU, CVU o alias): "
            "un CBU como número pierde los ceros de adelante."
        )
    return {"customer": customer, "amount": exact_amount, "destination": destination}


def _required_idempotency_key(value: object) -> str:
    if value is None:
        raise TypeError(
            "psp.transfers.create necesita idempotency_key: generá un UUID v4 con "
            "str(uuid.uuid4()), guardalo con la transferencia antes de llamar y reusalo en cada "
            "reintento: psp.transfers.create(customer=customer, amount=amount, "
            "destination=destination, idempotency_key=idempotency_key)."
        )
    return validate_idempotency_key(value)


def _transfer_list_query(
    customer: str | None,
    direction: str | None,
    status: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "customer": customer,
            "direction": direction,
            "status": status,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


class PspCustomerService:
    """``client.psp.customers``: los clientes de tu empresa, cada uno con un CVU a su nombre.

    Usá un ``RayaClient`` con tu clave secreta (``raya_sk_live_…``), siempre desde tu servidor.
    Crear clientes y cambiar su estado exige Raya PSP activado: hasta que lo aprobemos,
    ``PermissionDeniedError`` con ``code == "PSP_NOT_ACTIVATED"`` (bloquear no lo exige).
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    # create tiene tres formas, una por @overload: con Identidad (solo identity_verification), con
    # las fotos (persona humana) o una persona jurídica. La implementación lleva todo en None y
    # reenvía a _create, sin sobrecargas, que es lo que usa el estilo global (PspCustomer.create).

    @overload
    def create(
        self,
        *,
        identity_verification: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    def create(
        self,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["F"],
        document_front_url: str,
        document_back_url: str,
        selfie_url: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    def create(
        self,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["J"],
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    def create(
        self,
        *,
        identity_verification: str | None = None,
        tax_id: str | None = None,
        name: str | None = None,
        person_type: PspCustomerPersonType | None = None,
        document_front_url: str | None = None,
        document_back_url: str | None = None,
        selfie_url: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Crea un cliente con un CVU a su nombre (``POST /v1/psp/customers``), de una de tres
        formas:

        - **Con Identidad**, si tu cliente se verificó con Raya Identity: solo
          ``identity_verification`` (y, si querés, ``external_reference`` y ``metadata``).
          Tomamos de la verificación su CUIL (``tax_id``), su nombre y apellido del RENAPER
          (``name``), su sexo y su nacionalidad; ``person_type`` es ``F``. ``201`` con ``status``
          ``active`` (con el CVU y el alias) o ``failed``, o ``202`` con ``pending`` mientras
          terminamos de crear el CVU (o con ``verifying``, si lo tenemos que revisar).
        - **Con las fotos**, una persona humana que verificaste vos (tu propio KYC u otro
          proveedor): ``tax_id``, ``name``, ``person_type="F"``, ``document_front_url``,
          ``document_back_url`` y ``selfie_url``. ``202`` con ``verifying``: las bajamos, leemos
          el DNI (el sexo sale del frente), lo validamos contra el Registro Nacional de las
          Personas (RENAPER) y comparamos la cara. Si el DNI o el nombre no coinciden, queda
          ``rejected`` (``decline_reason.code``: ``document_mismatch`` o ``name_mismatch``).
        - **Una persona jurídica**: ``tax_id``, ``name`` (su razón social) y ``person_type="J"``,
          sin fotos. Validamos su CUIT y su razón social contra el Registro Nacional de
          Sociedades y queda en revisión (``202`` con ``verifying``).

        Con ``identity_verification`` no mandes ``tax_id``, ``name``, ``person_type`` ni las
        fotos: la API responde ``InvalidRequestError`` con ``PARAMETER_INVALID`` y el campo en
        ``error.param``. Lo que sigue en segundo plano te lo avisamos con
        ``psp.customer.activated``, ``psp.customer.failed`` o ``psp.customer.rejected``.
        ``customer.last_response.http_status`` dice si fue ``201`` o ``202``; decidí con
        ``status``.

        :param identity_verification: El ``id`` (``idv_…``) de una verificación ``document`` de
            tu cuenta en estado ``verified``, que no sea de la persona titular de tu cuenta y que
            no hayas usado para otro cliente (si no, ``ConflictError`` con
            ``CUSTOMER_ALREADY_EXISTS``). Si no tiene un CUIL válido, creá el cliente con las
            fotos.
        :param tax_id: Sin ``identity_verification``: su CUIL o CUIT, 11 dígitos sin guiones.
        :param name: Sin ``identity_verification``: su nombre y apellido o su razón social, de 2
            a 120 caracteres en una línea. La razón social tiene que coincidir con la del
            Registro Nacional de Sociedades (si no, ``UnprocessableEntityError`` con
            ``CUSTOMER_DATA_MISMATCH``).
        :param person_type: Sin ``identity_verification``: ``F`` (persona humana: un CUIL que
            empieza con 20, 23, 24 o 27) o ``J`` (persona jurídica: un CUIT que empieza con 30, 33
            o 34).
        :param document_front_url: Con las fotos: URL ``https://`` del frente del DNI (hasta 2048
            caracteres). Las imágenes, JPEG o PNG derechas, de hasta 5 MB.
        :param document_back_url: Con las fotos: URL ``https://`` del dorso del DNI.
        :param selfie_url: Con las fotos: URL ``https://`` de una selfie: una sola cara, de frente
            y sin anteojos.
        :param external_reference: Tu identificador del cliente: hasta 128 caracteres en una línea.
            No pongas datos personales: al filtrar la lista viaja en la URL.
        :param metadata: Hasta 20 pares clave-valor de texto.
        :param idempotency_key: Recomendada: una por alta, guardada con tu cliente, y la misma si
            reintentás. Si no la pasás, generamos una que protege los reintentos de esta llamada.
        """
        return self._create(
            identity_verification=identity_verification,
            tax_id=tax_id,
            name=name,
            person_type=person_type,
            document_front_url=document_front_url,
            document_back_url=document_back_url,
            selfie_url=selfie_url,
            external_reference=external_reference,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @overload
    async def create_async(
        self,
        *,
        identity_verification: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    async def create_async(
        self,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["F"],
        document_front_url: str,
        document_back_url: str,
        selfie_url: str,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    @overload
    async def create_async(
        self,
        *,
        tax_id: str,
        name: str,
        person_type: Literal["J"],
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer: ...

    async def create_async(
        self,
        *,
        identity_verification: str | None = None,
        tax_id: str | None = None,
        name: str | None = None,
        person_type: PspCustomerPersonType | None = None,
        document_front_url: str | None = None,
        document_back_url: str | None = None,
        selfie_url: str | None = None,
        external_reference: str | None = None,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Como ``create()``, para asyncio."""
        return await self._create_async(
            identity_verification=identity_verification,
            tax_id=tax_id,
            name=name,
            person_type=person_type,
            document_front_url=document_front_url,
            document_back_url=document_back_url,
            selfie_url=selfie_url,
            external_reference=external_reference,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    def _create(
        self,
        *,
        identity_verification: str | None,
        tax_id: str | None,
        name: str | None,
        person_type: PspCustomerPersonType | None,
        document_front_url: str | None,
        document_back_url: str | None,
        selfie_url: str | None,
        external_reference: str | None,
        metadata: Mapping[str, str] | None,
        idempotency_key: str | None,
        options: RequestOptions | None,
    ) -> PspCustomer:
        """``create()`` sin las sobrecargas, para reenviar valores que pueden ser ``None``."""
        return cast(
            PspCustomer,
            self._requestor.request(
                "POST",
                _CUSTOMERS,
                body=_create_customer_body(
                    identity_verification,
                    tax_id,
                    name,
                    person_type,
                    document_front_url,
                    document_back_url,
                    selfie_url,
                    external_reference,
                    metadata,
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=PspCustomer,
            ),
        )

    async def _create_async(
        self,
        *,
        identity_verification: str | None,
        tax_id: str | None,
        name: str | None,
        person_type: PspCustomerPersonType | None,
        document_front_url: str | None,
        document_back_url: str | None,
        selfie_url: str | None,
        external_reference: str | None,
        metadata: Mapping[str, str] | None,
        idempotency_key: str | None,
        options: RequestOptions | None,
    ) -> PspCustomer:
        """Como ``_create()``, para asyncio."""
        return cast(
            PspCustomer,
            await self._requestor.request_async(
                "POST",
                _CUSTOMERS,
                body=_create_customer_body(
                    identity_verification,
                    tax_id,
                    name,
                    person_type,
                    document_front_url,
                    document_back_url,
                    selfie_url,
                    external_reference,
                    metadata,
                ),
                idempotency_key=idempotency_key,
                options=options,
                expected=PspCustomer,
            ),
        )

    def retrieve(self, customer_id: str, *, options: RequestOptions | None = None) -> PspCustomer:
        """Un cliente de tu cuenta (``GET /v1/psp/customers/:id``)."""
        return cast(
            PspCustomer,
            self._requestor.request(
                "GET", _customer_path(customer_id), options=options, expected=PspCustomer
            ),
        )

    async def retrieve_async(
        self, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomer:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            PspCustomer,
            await self._requestor.request_async(
                "GET", _customer_path(customer_id), options=options, expected=PspCustomer
            ),
        )

    def list(
        self,
        *,
        status: PspCustomerStatus | None = None,
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspCustomer]:
        """Tus clientes, del más nuevo al más viejo (``GET /v1/psp/customers``).

        Devuelve una página. Para recorrer todos: ``.auto_paging_iter()``. No se filtra por CUIL
        (sería un dato personal en la URL): usá ``external_reference``.

        :param status: ``verifying``, ``pending``, ``active`` (sin los bloqueados), ``blocked``,
            ``closed``, ``failed`` o ``rejected``.
        :param external_reference: Coincidencia exacta.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _customer_list_query(
            status, external_reference, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[PspCustomer]",
            self._requestor.request_list(_CUSTOMERS, query=query, options=options),
        )

    async def list_async(
        self,
        *,
        status: PspCustomerStatus | None = None,
        external_reference: str | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspCustomer]:
        """Como ``list()``, para asyncio."""
        query = _customer_list_query(
            status, external_reference, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[PspCustomer]",
            await self._requestor.request_list_async(_CUSTOMERS, query=query, options=options),
        )

    def retrieve_balance(
        self, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomerBalance:
        """El saldo de un cliente (``GET /v1/psp/customers/:id/balance``): ``available`` (su
        saldo) y ``transferable`` (lo que podés transferir ahora en su nombre: lo que alcance de su
        saldo y del tuyo, y ``0`` si no está ``active``; no tiene en cuenta su límite mensual, ver
        ``LIMIT_EXCEEDED``)."""
        return cast(
            PspCustomerBalance,
            self._requestor.request(
                "GET",
                _customer_path(customer_id, "/balance"),
                options=options,
                expected=PspCustomerBalance,
            ),
        )

    async def retrieve_balance_async(
        self, customer_id: str, *, options: RequestOptions | None = None
    ) -> PspCustomerBalance:
        """Como ``retrieve_balance()``, para asyncio."""
        return cast(
            PspCustomerBalance,
            await self._requestor.request_async(
                "GET",
                _customer_path(customer_id, "/balance"),
                options=options,
                expected=PspCustomerBalance,
            ),
        )

    # --- Acciones: POST /v1/psp/customers/:id/<acción>, sin body. ---------------------------

    def _action(
        self,
        action: PspCustomerAction,
        customer_id: str,
        idempotency_key: str | None,
        options: RequestOptions | None,
    ) -> PspCustomer:
        return cast(
            PspCustomer,
            self._requestor.request(
                "POST",
                _customer_path(customer_id, f"/{action}"),
                idempotency_key=idempotency_key,
                options=options,
                expected=PspCustomer,
            ),
        )

    async def _action_async(
        self,
        action: PspCustomerAction,
        customer_id: str,
        idempotency_key: str | None,
        options: RequestOptions | None,
    ) -> PspCustomer:
        return cast(
            PspCustomer,
            await self._requestor.request_async(
                "POST",
                _customer_path(customer_id, f"/{action}"),
                idempotency_key=idempotency_key,
                options=options,
                expected=PspCustomer,
            ),
        )

    def block(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Bloquea a un cliente (``POST /v1/psp/customers/:id/block``): sigue recibiendo
        transferencias, pero no puede enviar ni recrear su CVU.

        Se puede desde ``pending``, ``active``, ``closed`` o ``failed``, y no exige Raya PSP
        aprobado. Si ya lo bloqueaste, lo devuelve igual. Desde ``verifying`` o ``rejected``,
        ``ConflictError`` con ``code == "CUSTOMER_STATUS_CONFLICT"`` y su estado en
        ``error.data``. Te avisamos con ``psp.customer.blocked``.
        """
        return self._action("block", customer_id, idempotency_key, options)

    async def block_async(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Como ``block()``, para asyncio."""
        return await self._action_async("block", customer_id, idempotency_key, options)

    def unblock(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Levanta tu bloqueo de un cliente (``POST /v1/psp/customers/:id/unblock``).

        Si no lo bloqueaste, lo devuelve igual. Un bloqueo de Raya solo lo levantamos nosotros:
        ``ConflictError`` con ``code == "CUSTOMER_STATUS_CONFLICT"`` y ``error.data`` igual a
        ``{"status": "blocked", "blocked_by": "raya"}``. Te avisamos con
        ``psp.customer.unblocked``.
        """
        return self._action("unblock", customer_id, idempotency_key, options)

    async def unblock_async(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Como ``unblock()``, para asyncio."""
        return await self._action_async("unblock", customer_id, idempotency_key, options)

    def close(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Da de baja el CVU de un cliente ``active`` (``POST /v1/psp/customers/:id/close``).

        Queda ``closed``: deja de recibir en ese CVU y conserva su saldo (también si tiene) y su
        historial; lo podés recrear con ``recreate()``. Si lo bloqueaste, tu bloqueo se levanta.
        Si ya está ``closed``, lo devuelve igual. Desde ``verifying``, ``pending``, ``failed`` o
        ``rejected``, o con un bloqueo de Raya, ``ConflictError`` con
        ``code == "CUSTOMER_STATUS_CONFLICT"``. Te avisamos con ``psp.customer.closed``.
        """
        return self._action("close", customer_id, idempotency_key, options)

    async def close_async(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Como ``close()``, para asyncio."""
        return await self._action_async("close", customer_id, idempotency_key, options)

    def recreate(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Le crea un CVU nuevo a un cliente ``closed`` o ``failed``, sin bloqueos
        (``POST /v1/psp/customers/:id/recreate``).

        Conserva su ``id``, su saldo y su historial. Vuelve ``active`` (``200``, con el CVU y el
        alias), ``failed`` (``200``) o ``pending`` (``202``, mientras lo terminamos de crear: te
        avisamos con ``psp.customer.activated`` o ``psp.customer.failed``). Si ya está ``pending``,
        lo devuelve igual (``202``) sin otra alta. Desde ``active``, ``verifying``, ``rejected`` o
        ``blocked``, ``ConflictError`` con ``code == "CUSTOMER_STATUS_CONFLICT"``.
        """
        return self._action("recreate", customer_id, idempotency_key, options)

    async def recreate_async(
        self,
        customer_id: str,
        *,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> PspCustomer:
        """Como ``recreate()``, para asyncio."""
        return await self._action_async("recreate", customer_id, idempotency_key, options)


class PspTransferService:
    """``client.psp.transfers``: lo que reciben tus clientes y lo que transferís en su nombre.

    Las transferencias de tus clientes no aparecen en ``client.transfers`` ni emiten
    ``transfer.*``: llegan como ``psp.transfer.*``.
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
        *,
        customer: str,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> PspTransfer:
        """Transfiere pesos en nombre de un cliente, desde su CVU a un CBU, CVU o alias
        (``POST /v1/psp/transfers``).

        Tu saldo manda: tienen que alcanzar tu saldo disponible (si no,
        ``UnprocessableEntityError`` con ``INSUFFICIENT_BALANCE``, aunque tu cliente tenga saldo) y
        después el de tu cliente (``CUSTOMER_INSUFFICIENT_BALANCE``). Si el destino es una cuenta
        de Raya, vuelve ``completed``; si no, ``pending`` hasta que te avisamos con
        ``psp.transfer.sent`` o ``psp.transfer.failed``. La comisión (``fee``) se descuenta de tu
        saldo.

        :param customer: El ``id`` del cliente (``pspc_…``): tiene que estar ``active``.
        :param amount: Pesos, hasta 2 decimales (``18350.5``, ``Decimal("18350.50")``): lo que
            baja del saldo de tu cliente.
        :param destination: CBU o CVU (22 dígitos) o alias (6 a 20 caracteres).
        :param idempotency_key: Obligatoria. Un UUID v4 que guardás con la transferencia **antes**
            de llamar y reusás en cada reintento: así nunca se transfiere dos veces. Para volver a
            intentar una transferencia que terminó ``failed``, usá una clave nueva.
        """
        return cast(
            PspTransfer,
            self._requestor.request(
                "POST",
                _TRANSFERS,
                body=_create_transfer_body(customer, amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=PspTransfer,
            ),
        )

    async def create_async(
        self,
        *,
        customer: str,
        amount: Amount,
        destination: str,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> PspTransfer:
        """Como ``create()``, para asyncio."""
        return cast(
            PspTransfer,
            await self._requestor.request_async(
                "POST",
                _TRANSFERS,
                body=_create_transfer_body(customer, amount, destination),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=PspTransfer,
            ),
        )

    def retrieve(self, transfer_id: str, *, options: RequestOptions | None = None) -> PspTransfer:
        """Una transferencia de un cliente (``GET /v1/psp/transfers/:id``)."""
        return cast(
            PspTransfer,
            self._requestor.request(
                "GET", _transfer_path(transfer_id), options=options, expected=PspTransfer
            ),
        )

    async def retrieve_async(
        self, transfer_id: str, *, options: RequestOptions | None = None
    ) -> PspTransfer:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            PspTransfer,
            await self._requestor.request_async(
                "GET", _transfer_path(transfer_id), options=options, expected=PspTransfer
            ),
        )

    def list(
        self,
        *,
        customer: str | None = None,
        direction: PspTransferDirection | None = None,
        status: PspTransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspTransfer]:
        """Las transferencias de tus clientes, de la más nueva a la más vieja
        (``GET /v1/psp/transfers``): las que recibieron y las que enviaste en su nombre.

        Devuelve una página. Para recorrer todas: ``.auto_paging_iter()``.

        :param customer: Solo las de este cliente (``pspc_…``).
        :param direction: ``inbound`` (recibidas por el cliente) u ``outbound`` (enviadas en su
            nombre).
        :param status: ``pending``, ``completed``, ``failed`` o ``reversed``.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _transfer_list_query(
            customer, direction, status, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[PspTransfer]",
            self._requestor.request_list(_TRANSFERS, query=query, options=options),
        )

    async def list_async(
        self,
        *,
        customer: str | None = None,
        direction: PspTransferDirection | None = None,
        status: PspTransferStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[PspTransfer]:
        """Como ``list()``, para asyncio."""
        query = _transfer_list_query(
            customer, direction, status, created_gte, created_lt, limit, cursor
        )
        return cast(
            "ListObject[PspTransfer]",
            await self._requestor.request_list_async(_TRANSFERS, query=query, options=options),
        )


class PspBalanceService:
    """``client.psp.balance``: tu saldo y el de tus clientes."""

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def retrieve(self, *, options: RequestOptions | None = None) -> PspBalance:
        """Tu saldo y el de tus clientes (``GET /v1/psp/balance``): ``available`` es tu saldo
        disponible (el mismo de ``client.balance.retrieve()``; puede ser negativo) y
        ``customers_balance``, la suma de los saldos de tus clientes."""
        return cast(
            PspBalance,
            self._requestor.request("GET", _BALANCE, options=options, expected=PspBalance),
        )

    async def retrieve_async(self, *, options: RequestOptions | None = None) -> PspBalance:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            PspBalance,
            await self._requestor.request_async(
                "GET", _BALANCE, options=options, expected=PspBalance
            ),
        )


class PspService:
    """``client.psp``: Raya PSP, cuentas con CVU y alias a nombre de los clientes de tu empresa.

    Es para cuentas de empresa con Raya PSP activado (lo pedís desde Negocios › Raya PSP, en el
    dashboard). ``client.psp.customers`` crea los clientes y cambia su
    estado, ``client.psp.transfers`` transfiere en su nombre y lee lo que reciben, y
    ``client.psp.balance`` da tu saldo y el de tus clientes. Van con tu clave secreta; todavía no
    está disponible en el sandbox. Referencia: https://raya.cash/api/psp
    """

    customers: PspCustomerService
    transfers: PspTransferService
    balance: PspBalanceService

    def __init__(self, requestor: APIRequestor) -> None:
        self.customers = PspCustomerService(requestor)
        self.transfers = PspTransferService(requestor)
        self.balance = PspBalanceService(requestor)
