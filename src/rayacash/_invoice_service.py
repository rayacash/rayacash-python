"""``client.invoices``: el Facturador, facturas electrónicas que emitimos en ARCA a tu nombre.

Van con tu clave secreta. Los parámetros viajan en el orden de la API (``dni``, ``amount`` y
``metadata``; en la lista, ``status``, ``created_gte``, ``created_lt``, ``limit`` y ``cursor``) y
solo los que vinieron: los ``None`` se omiten.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rayacash._encoding import (
    Amount,
    canonical_amount,
    encode_query,
    path_id,
    validate_idempotency_key,
)
from rayacash._invoice import Invoice, InvoiceStatus
from rayacash._list_object import ListObject
from rayacash._request_options import RequestOptions

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor

_INVOICES = "/v1/invoices"


def _invoice_path(invoice_id: str) -> str:
    return f"{_INVOICES}/{path_id('invoice_id', invoice_id)}"


def _create_body(dni: str, amount: Amount, metadata: Mapping[str, str] | None) -> dict[str, Any]:
    """El body en el orden de la API (``dni``, ``amount``, ``metadata``), validado en ese mismo
    orden.

    Acá, solo las formas que nunca pueden andar: ``dni`` es texto (la API no acepta un número) y
    ``metadata``, un dict. Los dígitos del DNI y el rango del monto los responde la API con
    ``data.field``.
    """
    if not isinstance(dni, str):
        # El mismo texto que la API (PARAMETER_INVALID) y que los SDKs de Node y PHP.
        raise TypeError(
            'dni tiene que ser un DNI de 6 a 8 dígitos, como texto (por ejemplo, "12345678").'
        )
    exact_amount = canonical_amount(amount)
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError('metadata tiene que ser un dict de str a str, como {"pedido": "1042"}.')
    return {"dni": dni, "amount": exact_amount, "metadata": metadata}


def _required_idempotency_key(value: object) -> str:
    if value is None:
        raise TypeError(
            "invoices.create necesita idempotency_key: generá un UUID v4 con str(uuid.uuid4()), "
            "guardalo con la venta antes de llamar y reusalo en cada reintento: "
            "invoices.create(dni=dni, amount=amount, idempotency_key=idempotency_key)."
        )
    return validate_idempotency_key(value)


def _list_query(
    status: str | None,
    created_gte: str | datetime | None,
    created_lt: str | datetime | None,
    limit: int | None,
    cursor: str | None,
) -> dict[str, str]:
    return encode_query(
        {
            "status": status,
            "created_gte": created_gte,
            "created_lt": created_lt,
            "limit": limit,
            "cursor": cursor,
        }
    )


class InvoiceService:
    """``client.invoices``: el Facturador, facturas electrónicas que emitimos en ARCA a tu nombre.

    Antes, configuralo en Negocios › Facturador, en el dashboard: el punto de venta, el
    certificado y la clave privada de ARCA, tu condición frente al IVA y el concepto. Usá un
    ``RayaClient`` con tu clave secreta (``raya_sk_live_…``), siempre desde tu servidor. Todavía no
    está disponible en el sandbox. Referencia: https://raya.cash/api/invoices
    """

    def __init__(self, requestor: APIRequestor) -> None:
        self._requestor = requestor

    def create(
        self,
        *,
        dni: str,
        amount: Amount,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Invoice:
        """Crea una factura electrónica a nombre de quien te compra (``POST /v1/invoices``).

        Responde enseguida (``202``) con la factura en ``pending`` y la emitimos en ARCA en segundo
        plano: te avisamos con ``invoice.issued`` (ARCA la autorizó y le asignó su CAE),
        ``invoice.rejected`` (ARCA la rechazó) o ``invoice.failed`` (no pudimos emitirla). También
        la podés consultar con ``retrieve()``.

        Es una Factura B (con el IVA del 21 % incluido en ``amount``) si sos Responsable Inscripto
        o una Factura C (sin IVA) si sos monotributista, a un consumidor final: el tipo, el punto
        de venta y el concepto salen de lo que configuraste en Negocios › Facturador. Si el
        Facturador no está listo para emitir, ``PermissionDeniedError`` con
        ``code == "FACTURADOR_NOT_READY"`` y el motivo en ``error.data["reason"]``
        (``not_configured``, ``checking``, ``action_required``, ``certificate_expired`` o
        ``disabled``).

        :param dni: El DNI de quien te compra, como texto: de 6 a 8 dígitos, como ``"12345678"``.
        :param amount: El total, en pesos y con hasta 2 decimales (``15000``,
            ``Decimal("15000.50")``): en una Factura B, con el IVA incluido y de al menos ``0.03``
            (con menos, el IVA da cero: ``PARAMETER_INVALID``).
        :param metadata: Hasta 20 pares clave-valor de texto.
        :param idempotency_key: Obligatoria. Un UUID v4 que guardás con la venta **antes** de
            llamar y reusás en cada reintento: así nunca se emiten dos facturas por la misma venta.
            Para volver a intentar una factura que terminó ``rejected`` o ``failed``, usá una
            clave nueva.
        """
        return cast(
            Invoice,
            self._requestor.request(
                "POST",
                _INVOICES,
                body=_create_body(dni, amount, metadata),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=Invoice,
            ),
        )

    async def create_async(
        self,
        *,
        dni: str,
        amount: Amount,
        metadata: Mapping[str, str] | None = None,
        idempotency_key: str,
        options: RequestOptions | None = None,
    ) -> Invoice:
        """Como ``create()``, para asyncio."""
        return cast(
            Invoice,
            await self._requestor.request_async(
                "POST",
                _INVOICES,
                body=_create_body(dni, amount, metadata),
                idempotency_key=_required_idempotency_key(idempotency_key),
                options=options,
                expected=Invoice,
            ),
        )

    def retrieve(self, invoice_id: str, *, options: RequestOptions | None = None) -> Invoice:
        """Una factura (``GET /v1/invoices/:id``): su estado y, cuando está ``issued``, su número
        y su CAE."""
        return cast(
            Invoice,
            self._requestor.request(
                "GET", _invoice_path(invoice_id), options=options, expected=Invoice
            ),
        )

    async def retrieve_async(
        self, invoice_id: str, *, options: RequestOptions | None = None
    ) -> Invoice:
        """Como ``retrieve()``, para asyncio."""
        return cast(
            Invoice,
            await self._requestor.request_async(
                "GET", _invoice_path(invoice_id), options=options, expected=Invoice
            ),
        )

    def list(
        self,
        *,
        status: InvoiceStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Invoice]:
        """Tus facturas, de la más nueva a la más vieja (``GET /v1/invoices``).

        Devuelve una página. Para recorrer todas: ``.auto_paging_iter()``. No se filtra por DNI
        (sería un dato personal en la URL): guardá el ``id`` de cada factura con tu venta.

        :param status: ``pending``, ``issued``, ``rejected`` o ``failed``.
        :param created_gte: Desde este momento (incluido): ``datetime`` con zona o ISO 8601.
        :param created_lt: Hasta este momento (excluido). Con ``created_gte`` arma un rango
            semiabierto: los días o meses seguidos no se pisan.
        :param limit: De 1 a 100 por página (por defecto, 20).
        :param cursor: El ``next_cursor`` de la página anterior.
        """
        query = _list_query(status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[Invoice]",
            self._requestor.request_list(_INVOICES, query=query, options=options),
        )

    async def list_async(
        self,
        *,
        status: InvoiceStatus | None = None,
        created_gte: str | datetime | None = None,
        created_lt: str | datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        options: RequestOptions | None = None,
    ) -> ListObject[Invoice]:
        """Como ``list()``, para asyncio."""
        query = _list_query(status, created_gte, created_lt, limit, cursor)
        return cast(
            "ListObject[Invoice]",
            await self._requestor.request_list_async(_INVOICES, query=query, options=options),
        )
