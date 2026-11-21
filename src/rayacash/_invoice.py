"""El Facturador: las facturas electrónicas que emitimos en ARCA a tu nombre (``invoice``)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Literal

from rayacash._encoding import Amount
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._invoice_service import InvoiceService
    from rayacash._list_object import ListObject

#: ``B`` (si sos Responsable Inscripto: el IVA del 21 % va incluido en el monto) o ``C`` (si sos
#: monotributista: sin IVA).
InvoiceType = Literal["B", "C"]
InvoiceStatus = Literal["pending", "issued", "rejected", "failed"]
InvoiceConcept = Literal["products", "services", "products_and_services"]
InvoiceFailureCode = Literal[
    "arca_rejected",
    "facturador_not_ready",
    "not_issued",
    "numbering_conflict",
    "account_unavailable",
]
InvoiceArcaMessageType = Literal["error", "observation"]


def _service() -> InvoiceService:
    from rayacash._global import default_requestor
    from rayacash._invoice_service import InvoiceService

    return InvoiceService(default_requestor())


class Invoice(RayaObject):
    """Una factura electrónica que emitimos en ARCA a tu nombre: una Factura B o C a un consumidor
    final, identificado por su DNI.

    La creás con ``client.invoices.create(...)`` y queda ``pending`` mientras la emitimos. Dala por
    emitida solo cuando ``status`` es ``issued``: recién ahí trae su número y su CAE. Es el mismo
    objeto que llega en los webhooks ``invoice.*``.
    """

    OBJECT_NAME = "invoice"

    class FailureReason(RayaObject):
        """Por qué no se emitió (``rejected`` o ``failed``). Decidí con ``code``, no con
        ``message``."""

        #: En ``rejected``: ``arca_rejected`` (ARCA la rechazó: ``arca_messages`` dice por qué). En
        #: ``failed``: ``facturador_not_ready``, ``not_issued``, ``numbering_conflict`` o
        #: ``account_unavailable``. Pueden sumarse valores.
        code: InvoiceFailureCode
        #: El motivo en palabras, en castellano: puede cambiar.
        message: str

    class ArcaMessage(RayaObject):
        """Un error o una observación de ARCA sobre la factura, tal como lo devolvió."""

        #: ``error`` u ``observation``. Pueden sumarse valores.
        type: InvoiceArcaMessageType
        #: El código de ARCA.
        code: int
        #: El texto de ARCA, sin cambios.
        message: str

    _inner_class_types: ClassVar[dict[str, type[RayaObject]]] = {
        "failure_reason": FailureReason,
        "arca_messages": ArcaMessage,
    }
    _plain_fields: ClassVar[frozenset[str]] = frozenset({"metadata"})

    # Los campos van antes de los classmethods: después de ``def list`` (abajo), ``list[...]``
    # sería ese método para mypy.

    #: ``inv_`` y 24 letras o números.
    id: str
    object: Literal["invoice"]
    #: ``B`` (Responsable Inscripto, con el IVA incluido) o ``C`` (Monotributo, sin IVA), según la
    #: condición frente al IVA que configuraste en Negocios › Facturador.
    type: InvoiceType
    #: ``pending`` (la estamos emitiendo), ``issued`` (ARCA la autorizó y le asignó su CAE),
    #: ``rejected`` (ARCA la rechazó) o ``failed`` (no pudimos emitirla y no quedó registrada en
    #: ARCA). Pueden sumarse valores.
    status: InvoiceStatus
    #: El total de la factura, en pesos: lo que mandaste en ``amount``.
    amount: float
    #: El importe neto, en pesos. En una Factura B, ``amount`` sin el IVA; en una C, igual a
    #: ``amount``.
    net_amount: float
    #: El IVA, en pesos: ``amount`` menos ``net_amount``. ``None`` en una Factura C.
    vat_amount: float | None
    #: Siempre ``"ARS"``.
    currency: str
    #: El DNI de quien te compra, sin puntos.
    dni: str
    #: El punto de venta con el que la emitimos.
    point_of_sale: int
    #: El número del comprobante en ese punto de venta. ``None`` si no está ``issued``.
    number: int | None
    #: ``products``, ``services`` o ``products_and_services``, según el concepto que configuraste.
    concept: InvoiceConcept
    #: El CAE (Código de Autorización Electrónico) de 14 dígitos que le asignó ARCA. ``None`` si no
    #: está ``issued``.
    cae: str | None
    #: Hasta cuándo vale el CAE (``YYYY-MM-DD``). ``None`` si no está ``issued``.
    cae_expires_on: str | None
    #: La fecha del comprobante registrada en ARCA (``YYYY-MM-DD``). ``None`` si no está
    #: ``issued``.
    issued_on: str | None
    #: Por qué no se emitió; ``None`` si su ``status`` no es ``rejected`` ni ``failed``.
    failure_reason: FailureReason | None
    #: Los errores y las observaciones de ARCA, tal como los devolvió (hasta 20). ``[]`` si no hay.
    arca_messages: list[ArcaMessage]
    #: Tus pares clave-valor (un dict común). ``{}`` si no mandaste ninguno.
    metadata: dict[str, str]
    #: Cuándo la emitimos (ISO 8601 en UTC). ``None`` si no está ``issued``.
    issued_at: str | None
    #: Cuándo la creaste (ISO 8601 en UTC), como ``"2026-11-18T14:30:05Z"``.
    created_at: str

    # --- Estilo global (rayacash.Invoice.*); ver InvoiceService para el detalle. ---------------

    @classmethod
    def create(
        cls,
        *,
        dni: str,
        amount: Amount,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Invoice:
        """Crea una factura con tu clave secreta en ``rayacash.api_key`` (o en
        ``options["api_key"]``). ``idempotency_key`` es obligatoria."""
        return _service().create(
            dni=dni,
            amount=amount,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    async def create_async(
        cls,
        *,
        dni: str,
        amount: Amount,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Invoice:
        return await _service().create_async(
            dni=dni,
            amount=amount,
            metadata=metadata,
            idempotency_key=idempotency_key,
            options=options,
        )

    @classmethod
    def retrieve(cls, invoice_id: str, *, options: RequestOptions | None = None) -> Invoice:
        return _service().retrieve(invoice_id, options=options)

    @classmethod
    async def retrieve_async(
        cls, invoice_id: str, *, options: RequestOptions | None = None
    ) -> Invoice:
        return await _service().retrieve_async(invoice_id, options=options)

    @classmethod
    def list(
        cls,
        *,
        status: InvoiceStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Invoice]:
        return _service().list(
            status=status,
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
        status: InvoiceStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Invoice]:
        return await _service().list_async(
            status=status,
            created_gte=created_gte,
            created_lt=created_lt,
            limit=limit,
            cursor=cursor,
            options=options,
        )
