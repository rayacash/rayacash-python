"""Raya PSP: los pedidos de documentación sobre un cliente (``psp.document_request``)."""

from __future__ import annotations

from typing_extensions import Literal

from rayacash._raya_object import RayaObject

PspDocumentRequestStatus = Literal["open", "submitted", "closed"]


class PspDocumentRequest(RayaObject):
    """Un pedido de documentación sobre un cliente de Raya PSP.

    A veces nuestro equipo de cumplimiento necesita documentación sobre un cliente: te avisamos
    con el webhook ``psp.document_request.created`` (y un email) y la subís desde Negocios › Raya
    PSP, en el dashboard. Cuando lo cerramos, te avisamos con ``psp.document_request.closed``. Solo
    llega en los eventos: la API no tiene un endpoint para leerlo.
    """

    OBJECT_NAME = "psp.document_request"

    #: ``pspd_`` y 24 letras o números.
    id: str
    object: Literal["psp.document_request"]
    #: El ``id`` del cliente (``pspc_…``).
    customer: str
    #: ``open`` (falta la documentación), ``submitted`` (la mandaste) o ``closed`` (lo cerramos).
    #: Pueden sumarse valores.
    status: PspDocumentRequestStatus
    #: El tema del pedido, hasta 120 caracteres.
    subject: str
    #: Lo que te pedimos, escrito para vos: hasta 2000 caracteres.
    message: str
    #: Cuándo lo creamos (ISO 8601 en UTC).
    created_at: str
    #: Cuándo mandaste la documentación, o ``None``.
    submitted_at: str | None
    #: Cuándo lo cerramos, o ``None``.
    closed_at: str | None
