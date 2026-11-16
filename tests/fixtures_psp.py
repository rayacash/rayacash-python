"""Los objetos de ejemplo de Raya PSP (api.md › Raya PSP), con datos sintéticos.

Son los JSON que muestra raya.cash/api/psp (API_REFERENCE_PSP_EXAMPLES de
utils/apiReferencePagePsp.ts y API_REFERENCE_PSP_DEMO de utils/apiReferenceRequestsPsp.ts, en la
web): los tres SDKs testean con los mismos vectores. El CUIL y el CUIT llevan el verificador
inválido a propósito, el alias lleva guion bajo (un alias real no lo admite) y los CVU son los
demoCvu de la web ("api-reference-psp-cliente", "api-reference-psp-empresa",
"api-reference-psp-cliente-nuevo" y "api-reference-proveedor"). Los montos no dejan deducir
ningún porcentaje de comisión. Los estados que la referencia no muestra (pending, rejected,
failed, una transferencia fallida, un pedido cerrado) salen de los mismos objetos. CREATE_BODY
y PHOTOS_BODY son los dos bodies de Crear un cliente de esa página: el de la request de ejemplo
(con Identidad, solo identity_verification) y el de «Con las fotos» (sin gender: el sexo sale del
frente del DNI).
"""

from __future__ import annotations

from typing import Any

from tests.fixtures_identity import VERIFICATION_ID

CUSTOMER_ID = "pspc_7Hq2Lm9Xw4Tz1Bv8Nc3Kd6Rf"
COMPANY_ID = "pspc_5Ns1Ve8Jt3Wd0Hx6Pq9Bk2Gm"
OUTBOUND_ID = "pspt_4Wm8Qd2Zr6Yk0Ps3Hj7Ln1Cx"
INBOUND_ID = "pspt_9Bf5Tn2Gv8Xc4Mr0Ka6Wq3Ez"
DOCUMENT_REQUEST_ID = "pspd_2Kx7Rb4Np9Va1Dm6Ys3Lh8Qt"
TAX_ID = "27123456781"
COMPANY_TAX_ID = "30712345672"
CUSTOMER_NAME = "María Laura Ejemplo"
COMPANY_NAME = "Distribuidora Ejemplo S. A."
CUSTOMER_ACCOUNT = "0000123300537571545575"
COMPANY_ACCOUNT = "0000123300557880122458"
RECREATED_ACCOUNT = "0000123337002711594589"
SUPPLIER_ACCOUNT = "0000123380736153041182"
PHOTO_URLS = {
    "document_front_url": "https://archivos.example.com/kyc/frente.jpg?firma=ejemplo",
    "document_back_url": "https://archivos.example.com/kyc/dorso.jpg?firma=ejemplo",
    "selfie_url": "https://archivos.example.com/kyc/selfie.jpg?firma=ejemplo",
}

# Crear un cliente, en el orden de CREATE_FIELDS de la API: con Identidad alcanza la verificación
# (su CUIL, su nombre y su sexo salen de ahí); sin ella, los datos y las fotos de una persona
# humana que verificaste vos.
CREATE_BODY: dict[str, Any] = {
    "identity_verification": VERIFICATION_ID,
    "external_reference": "cliente-8812",
    "metadata": {"plan": "pro"},
}
PHOTOS_BODY: dict[str, Any] = {
    "tax_id": TAX_ID,
    "name": CUSTOMER_NAME,
    "person_type": "F",
    **PHOTO_URLS,
    "external_reference": "cliente-8812",
}

# Los mensajes de los 7 códigos de Raya PSP, literales de publicapi/errors.py de la API.
ERROR_MESSAGES = {
    "PSP_NOT_ACTIVATED": (
        "Raya PSP todavía no está activado para tu cuenta. Activalo o mirá el estado de tu "
        "solicitud en Negocios › Raya PSP."
    ),
    "CUSTOMER_NOT_FOUND": "No encontramos ese cliente.",
    "CUSTOMER_ALREADY_EXISTS": "Ya tenés un cliente con ese CUIL o CUIT.",
    "CUSTOMER_STATUS_CONFLICT": (
        "El cliente no está en un estado que permita esta operación. Revisá su status."
    ),
    "CUSTOMER_INSUFFICIENT_BALANCE": (
        "Tu cliente no tiene saldo suficiente para esta transferencia."
    ),
    "CUSTOMER_DATA_MISMATCH": "Los datos del cliente no coinciden con los registros oficiales.",
    "TAX_ID_NOT_REGISTERED": "No encontramos ese CUIT en el Registro Nacional de Sociedades.",
}

_CVU: dict[str, Any] = {
    "account": CUSTOMER_ACCOUNT,
    "alias": "maria_ejemplo",
    "holder_name": "MARIA LAURA EJEMPLO",
    "status": "active",
    "created_at": "2026-10-24T11:02:16Z",
    "closed_at": None,
}

# La persona humana de los ejemplos después de sus dos movimientos: recibió 42000 y le
# transferiste 18350.5 en su nombre (42000 - 18350.5 = 23649.5).
CUSTOMER_WITH_BALANCE: dict[str, Any] = {
    "id": CUSTOMER_ID,
    "object": "psp.customer",
    "status": "active",
    "person_type": "F",
    "tax_id": TAX_ID,
    "name": CUSTOMER_NAME,
    "balance": 23649.5,
    "currency": "ARS",
    "cvu": _CVU,
    "blocked_by": None,
    "identity_verification": VERIFICATION_ID,
    "decline_reason": None,
    "external_reference": "cliente-8812",
    "metadata": {"plan": "pro"},
    "created_at": "2026-10-24T11:02:14Z",
}

# La respuesta de Crear un cliente con una verificación de Identidad: 201, con el CVU y el alias y
# sin saldo.
CUSTOMER_ACTIVE: dict[str, Any] = {**CUSTOMER_WITH_BALANCE, "balance": 0}

# 202: creando el CVU (todavía sin número).
CUSTOMER_PENDING: dict[str, Any] = {**CUSTOMER_ACTIVE, "status": "pending", "cvu": None}

# 202: con las fotos, mientras validamos la identidad.
CUSTOMER_VERIFYING: dict[str, Any] = {
    **CUSTOMER_ACTIVE,
    "status": "verifying",
    "cvu": None,
    "identity_verification": None,
    "metadata": {},
}

CUSTOMER_REJECTED: dict[str, Any] = {
    **CUSTOMER_VERIFYING,
    "status": "rejected",
    "decline_reason": {
        "code": "face_mismatch",
        "message": "No pudimos confirmar que la selfie sea de la misma persona del DNI.",
    },
}

CUSTOMER_FAILED: dict[str, Any] = {
    **CUSTOMER_PENDING,
    "status": "failed",
    "decline_reason": {
        "code": "bank_rejected",
        "message": "El banco rechazó el alta del CVU. Podés volver a intentarlo con recrear.",
    },
}

CUSTOMER_BLOCKED: dict[str, Any] = {
    **CUSTOMER_WITH_BALANCE,
    "status": "blocked",
    "blocked_by": "account",
}

# Dado de baja: el CVU queda closing hasta que el banco confirma la baja.
CUSTOMER_CLOSED: dict[str, Any] = {
    **CUSTOMER_WITH_BALANCE,
    "status": "closed",
    "cvu": {**_CVU, "status": "closing", "closed_at": "2026-10-24T16:40:03Z"},
}

# Recreado: el mismo id y el mismo saldo, con un CVU y un alias nuevos.
CUSTOMER_RECREATED: dict[str, Any] = {
    **CUSTOMER_WITH_BALANCE,
    "cvu": {
        **_CVU,
        "account": RECREATED_ACCOUNT,
        "alias": "maria_ejemplo_nuevo",
        "created_at": "2026-10-24T17:15:42Z",
    },
}

# La persona jurídica del listado, ya revisada (23649.5 + 489225.75 = 512875.25, el
# customers_balance de PSP_BALANCE).
COMPANY: dict[str, Any] = {
    **CUSTOMER_WITH_BALANCE,
    "id": COMPANY_ID,
    "person_type": "J",
    "tax_id": COMPANY_TAX_ID,
    "name": COMPANY_NAME,
    "balance": 489225.75,
    "cvu": {
        **_CVU,
        "account": COMPANY_ACCOUNT,
        "alias": "distri_ejemplo",
        "holder_name": "DISTRIBUIDORA EJEMPLO S. A.",
        "created_at": "2026-10-24T15:20:31Z",
    },
    "identity_verification": None,
    "external_reference": "cliente-8813",
    "metadata": {},
    "created_at": "2026-10-24T13:41:09Z",
}

# La misma empresa recién creada: sin prueba biométrica y en revisión (202 verifying).
COMPANY_VERIFYING: dict[str, Any] = {**COMPANY, "status": "verifying", "balance": 0, "cvu": None}

CUSTOMER_LIST: dict[str, Any] = {
    "object": "list",
    "data": [COMPANY, CUSTOMER_WITH_BALANCE],
    "has_more": False,
    "next_cursor": None,
}

CUSTOMER_BALANCE: dict[str, Any] = {
    "object": "psp.customer_balance",
    "customer": CUSTOMER_ID,
    "available": 23649.5,
    "transferable": 23649.5,
    "currency": "ARS",
}

PSP_BALANCE: dict[str, Any] = {
    "object": "psp.balance",
    "available": 640200.5,
    "customers_balance": 512875.25,
    "currency": "ARS",
}

# Enviada en nombre del cliente a otra entidad: la comisión, a propósito, no es un porcentaje
# redondo del monto.
TRANSFER_OUTBOUND_PENDING: dict[str, Any] = {
    "id": OUTBOUND_ID,
    "object": "psp.transfer",
    "customer": CUSTOMER_ID,
    "direction": "outbound",
    "status": "pending",
    "amount": 18350.5,
    "fee": 61.37,
    "net_amount": 18289.13,
    "currency": "ARS",
    "account": CUSTOMER_ACCOUNT,
    "counterparty": {
        "name": "Proveedora Ejemplo S. A.",
        "tax_id": "30123456782",
        "account": SUPPLIER_ACCOUNT,
        "alias": "proveedor.ejemplo",
    },
    "description": "Transferencia",
    "reference": None,
    "created_at": "2026-10-24T14:30:05Z",
}

TRANSFER_OUTBOUND_COMPLETED: dict[str, Any] = {
    **TRANSFER_OUTBOUND_PENDING,
    "status": "completed",
    "reference": "P3W7K1N9X5Q2T8R4V6Z0MC",
}

TRANSFER_FAILED: dict[str, Any] = {**TRANSFER_OUTBOUND_PENDING, "status": "failed"}

# Recibida desde otra entidad: description es la del aviso del banco.
TRANSFER_INBOUND: dict[str, Any] = {
    "id": INBOUND_ID,
    "object": "psp.transfer",
    "customer": CUSTOMER_ID,
    "direction": "inbound",
    "status": "completed",
    "amount": 42000,
    "fee": 133.9,
    "net_amount": 41866.1,
    "currency": "ARS",
    "account": CUSTOMER_ACCOUNT,
    "counterparty": {
        "name": "Juan Ejemplo",
        "tax_id": "20123456785",
        "account": "0000123319112992888845",
        "alias": None,
    },
    "description": "Varios",
    "reference": "H6T2Y9P4W1K7N3X8Q5R0ZB",
    "created_at": "2026-10-24T12:05:47Z",
}

TRANSFER_LIST: dict[str, Any] = {
    "object": "list",
    "data": [TRANSFER_OUTBOUND_COMPLETED, TRANSFER_INBOUND],
    "has_more": False,
    "next_cursor": None,
}

DOCUMENT_REQUEST_OPEN: dict[str, Any] = {
    "id": DOCUMENT_REQUEST_ID,
    "object": "psp.document_request",
    "customer": CUSTOMER_ID,
    "status": "open",
    "subject": "Origen de los fondos",
    "message": (
        "Necesitamos un comprobante del origen de la transferencia que recibió este cliente el "
        "24 de octubre, como una factura o un recibo."
    ),
    "created_at": "2026-10-24T18:20:00Z",
    "submitted_at": None,
    "closed_at": None,
}

DOCUMENT_REQUEST_CLOSED: dict[str, Any] = {
    **DOCUMENT_REQUEST_OPEN,
    "status": "closed",
    "submitted_at": "2026-10-25T10:15:00Z",
    "closed_at": "2026-10-26T09:00:00Z",
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


# El de la referencia (Eventos de Raya PSP): un cliente recibió una transferencia.
EVENT_TRANSFER_RECEIVED = _event(
    "evt_2Hn8Wq5Tz1Kc7Vb4Xm9Rd3Lp",
    "psp.transfer.received",
    "2026-10-24T12:05:47Z",
    TRANSFER_INBOUND,
)
EVENT_CUSTOMER_ACTIVATED = _event(
    "evt_5pR8vN2kX7mQ1tW4zC9bH6jL",
    "psp.customer.activated",
    "2026-10-24T11:02:16Z",
    CUSTOMER_ACTIVE,
)
EVENT_DOCUMENT_REQUEST_CREATED = _event(
    "evt_3mJ9tR5vW2kP8xN1cQ6zL4bY",
    "psp.document_request.created",
    "2026-10-24T18:20:00Z",
    DOCUMENT_REQUEST_OPEN,
)


def customer_page(ids: list[str], *, next_cursor: str | None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{**CUSTOMER_WITH_BALANCE, "id": customer_id} for customer_id in ids],
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


def transfer_page(ids: list[str], *, next_cursor: str | None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{**TRANSFER_INBOUND, "id": transfer_id} for transfer_id in ids],
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }
