"""Los objetos de ejemplo del Facturador (api.md › Facturador), con datos sintéticos.

Usan los datos de ejemplo de la documentación (raya.cash/api/invoices): DNI "12345678", 15000
pesos, punto de venta 5, Factura B y CAE "76543210987654". En la Factura B, el neto es
(total / 1.21) redondeado a centavos (mitad a par) y el IVA, el total menos el neto: la suma da
exacta. Los textos de los errores y de failure_reason.message son los literales de la API (los
mismos en los tres SDKs); los de arca_messages son de ejemplo (ARCA manda los suyos). Se importa
como ``from tests import fixtures_facturador as facturador``.
"""

from __future__ import annotations

import re
from typing import Any

INVOICE_ID = "inv_8Tq3Wm6Xz1Kb4Nr7Pd2Lf9Hc"
PREVIOUS_ID = "inv_5Hc1Vt8Qw3Ny6Kr0Pb4Xm7Ld"
INVOICE_C_ID = "inv_2Rv7Kp4Yn9Ld1Gs6Wx3Bz8Mh"
DNI = "12345678"
CAE = "76543210987654"

#: El DNI que acepta la API, después de sacarle espacios, puntos, guiones y los ceros de adelante:
#: la misma regla en la API y en los tests de los tres SDK. El SDK no la aplica: manda el string
#: tal cual y responde la API.
DNI_PATTERN = re.compile(r"^[1-9][0-9]{5,7}$")
#: El 400 PARAMETER_INVALID de un dni que no cumple la regla (data.field = "dni").
DNI_INVALID_MESSAGE = (
    'dni tiene que ser un DNI de 6 a 8 dígitos, como texto (por ejemplo, "12345678").'
)

# Crear una factura, en el orden de la API: dni, amount y metadata.
CREATE_BODY: dict[str, Any] = {"dni": DNI, "amount": 15000, "metadata": {"pedido": "1042"}}

# Los mensajes de los 2 códigos del Facturador, literales de publicapi/errors.py de la API.
ERROR_MESSAGES = {
    "FACTURADOR_NOT_READY": (
        "El Facturador todavía no está listo para emitir facturas. Configuralo o mirá su estado "
        "en Negocios › Facturador."
    ),
    "INVOICE_NOT_FOUND": "No encontramos esa factura.",
}

# Los motivos de FACTURADOR_NOT_READY, en data.reason.
NOT_READY_REASONS = (
    "not_configured",
    "checking",
    "action_required",
    "certificate_expired",
    "disabled",
)

# failure_reason.message de cada failure_reason.code, literal de la API.
FAILURE_MESSAGES = {
    "arca_rejected": "ARCA rechazó la factura: arca_messages dice por qué.",
    "facturador_not_ready": (
        "Tu Facturador no estaba listo para emitirla. Revisalo en Negocios › Facturador y creá "
        "la factura de nuevo."
    ),
    "not_issued": "No pudimos emitirla y no quedó registrada en ARCA. Creala de nuevo.",
    "numbering_conflict": (
        "Otro sistema emitió comprobantes con el mismo punto de venta. Usá un punto de venta solo "
        "para Raya y creá la factura de nuevo."
    ),
    "account_unavailable": (
        "Tu cuenta no puede emitir facturas en este momento. Escribinos a soporte@raya.cash."
    ),
}

# 202: recién creada, mientras la emitimos. Factura B: 15000 = 12396.69 + 2603.31.
INVOICE_PENDING: dict[str, Any] = {
    "id": INVOICE_ID,
    "object": "invoice",
    "type": "B",
    "status": "pending",
    "amount": 15000,
    "net_amount": 12396.69,
    "vat_amount": 2603.31,
    "currency": "ARS",
    "dni": DNI,
    "point_of_sale": 5,
    "number": None,
    "concept": "products",
    "cae": None,
    "cae_expires_on": None,
    "issued_on": None,
    "failure_reason": None,
    "arca_messages": [],
    "metadata": {"pedido": "1042"},
    "issued_at": None,
    "created_at": "2026-11-18T14:30:05Z",
}

# ARCA la autorizó: con su número y su CAE.
INVOICE_ISSUED: dict[str, Any] = {
    **INVOICE_PENDING,
    "status": "issued",
    "number": 1234,
    "cae": CAE,
    "cae_expires_on": "2026-11-28",
    "issued_on": "2026-11-18",
    "issued_at": "2026-11-18T14:30:09Z",
}

# Una anterior de la misma cuenta, sin metadata: 8470 = 7000 + 1470.
INVOICE_PREVIOUS: dict[str, Any] = {
    **INVOICE_ISSUED,
    "id": PREVIOUS_ID,
    "amount": 8470,
    "net_amount": 7000,
    "vat_amount": 1470,
    "number": 1233,
    "cae": "76543210987653",
    "metadata": {},
    "issued_at": "2026-11-18T12:02:31Z",
    "created_at": "2026-11-18T12:02:27Z",
}

# ARCA la rechazó: no tiene número ni CAE, y arca_messages dice por qué.
INVOICE_REJECTED: dict[str, Any] = {
    **INVOICE_PENDING,
    "status": "rejected",
    "failure_reason": {"code": "arca_rejected", "message": FAILURE_MESSAGES["arca_rejected"]},
    "arca_messages": [
        {
            "type": "observation",
            "code": 10015,
            "message": "El campo DocNro es inválido para el tipo de documento informado.",
        }
    ],
}

# No pudimos emitirla y no quedó registrada en ARCA.
INVOICE_FAILED: dict[str, Any] = {
    **INVOICE_PENDING,
    "status": "failed",
    "failure_reason": {"code": "not_issued", "message": FAILURE_MESSAGES["not_issued"]},
}

# La de un monotributista: Factura C, sin IVA (el neto es el total), por servicios.
INVOICE_C_ISSUED: dict[str, Any] = {
    **INVOICE_ISSUED,
    "id": INVOICE_C_ID,
    "type": "C",
    "net_amount": 15000,
    "vat_amount": None,
    "number": 88,
    "concept": "services",
    "cae": "76543210981234",
    "metadata": {},
}

INVOICE_LIST: dict[str, Any] = {
    "object": "list",
    "data": [INVOICE_ISSUED, INVOICE_PREVIOUS],
    "has_more": False,
    "next_cursor": None,
}


def _event(event_id: str, event_type: str, created_at: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event_id,
        "object": "event",
        "type": event_type,
        "api_version": "2026-10-23",
        "created_at": created_at,
        "livemode": True,
        "data": {"object": obj},
    }


EVENT_INVOICE_ISSUED = _event(
    "evt_6Gk2Pq8Wm4Zt1Rx7Nb3Lc9Vh", "invoice.issued", "2026-11-18T14:30:09Z", INVOICE_ISSUED
)
EVENT_INVOICE_REJECTED = _event(
    "evt_9Wd4Hs1Kq7Bn3Tz6Lm2Xc8Pf", "invoice.rejected", "2026-11-18T14:30:08Z", INVOICE_REJECTED
)
EVENT_INVOICE_FAILED = _event(
    "evt_3Ln8Rv5Ty2Kh7Wq1Zd4Mb9Gs", "invoice.failed", "2026-11-19T14:30:05Z", INVOICE_FAILED
)


def invoice_page(ids: list[str], *, next_cursor: str | None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{**INVOICE_ISSUED, "id": invoice_id} for invoice_id in ids],
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }
