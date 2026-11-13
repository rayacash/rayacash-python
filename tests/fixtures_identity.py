"""Los objetos de ejemplo de Identidad (api.md › Identidad), con datos sintéticos.

Son los mismos JSON que muestra raya.cash/api/identity (utils/apiReferenceRequestsIdentity.ts de
la web y la referencia de la API): los tres SDKs testean con los mismos vectores. Los montos son
ilustrativos: nunca una tarifa real.
"""

from __future__ import annotations

from typing import Any

VERIFICATION_ID = "idv_3kT9vQ2mXw7Lp0aBcD4eF6gH"
BIOMETRIC_ID = "idv_8Zr2Nf6Kq1Yc5Wd9Ht3Jm7Pa"

VERIFICATION_PENDING: dict[str, Any] = {
    "id": VERIFICATION_ID,
    "object": "identity.verification",
    "type": "document",
    "status": "pending",
    "url": f"https://raya.cash/identity/{VERIFICATION_ID}",
    "external_reference": "cliente-8812",
    "metadata": {"plan": "pro"},
    "return_url": "https://tienda.example.com/cuenta",
    "reference": None,
    "decline_reason": None,
    "checks": {
        "document": {"status": "pending"},
        "liveness": {"status": "pending", "confidence": None},
        "face_match": {"status": "pending", "similarity": None},
        "registry": {"status": "pending", "data_match": None, "face_match": None},
    },
    "person": None,
    "amount": None,
    "currency": "ARS",
    "created_at": "2026-10-24T18:00:00Z",
    "started_at": None,
    "submitted_at": None,
    "completed_at": None,
    "expires_at": "2026-10-25T18:00:00Z",
}

PERSON: dict[str, Any] = {
    "first_name": "María Laura",
    "last_name": "Ejemplo",
    "document_type": "DNI",
    "document_number": "12345678",
    "sex": "F",
    "birth_date": "1990-01-31",
    "nationality": "Argentina",
    "cuil": "27123456781",
    "address": {
        "street": "Calle Ejemplo",
        "number": "1234",
        "floor": None,
        "apartment": None,
        "city": "Rosario",
        "municipality": "Rosario",
        "province": "Santa Fe",
        "postal_code": "2000",
        "country": "Argentina",
    },
    "document": {"copy": "A", "issue_date": "2020-01-31", "expiry_date": "2035-01-31"},
}

_STAMPS: dict[str, Any] = {
    "started_at": "2026-10-24T18:07:12Z",
    "submitted_at": "2026-10-24T18:09:40Z",
    "completed_at": "2026-10-24T18:09:58Z",
}

VERIFICATION_VERIFIED: dict[str, Any] = {
    **VERIFICATION_PENDING,
    "status": "verified",
    "checks": {
        "document": {"status": "passed"},
        "liveness": {"status": "passed", "confidence": 99.1},
        "face_match": {"status": "passed", "similarity": 97.4},
        "registry": {"status": "passed", "data_match": True, "face_match": "hit"},
    },
    "person": PERSON,
    "amount": 1000,
    **_STAMPS,
}

VERIFICATION_DECLINED: dict[str, Any] = {
    **VERIFICATION_PENDING,
    "status": "declined",
    "decline_reason": {
        "code": "registry_data_mismatch",
        "message": (
            "Los datos del documento no coinciden con los del Registro Nacional de las Personas "
            "(RENAPER)."
        ),
    },
    "checks": {
        "document": {"status": "passed"},
        "liveness": {"status": "passed", "confidence": 99.1},
        "face_match": {"status": "passed", "similarity": 97.4},
        "registry": {"status": "failed", "data_match": False, "face_match": None},
    },
    **_STAMPS,
}

VERIFICATION_CANCELED: dict[str, Any] = {
    **VERIFICATION_PENDING,
    "status": "canceled",
    "completed_at": "2026-10-24T18:30:00Z",
}

VERIFICATION_BIOMETRIC_VERIFIED: dict[str, Any] = {
    **VERIFICATION_VERIFIED,
    "id": BIOMETRIC_ID,
    "type": "biometric",
    "url": f"https://raya.cash/identity/{BIOMETRIC_ID}",
    "return_url": None,
    "reference": VERIFICATION_ID,
    "checks": {
        "document": {"status": "not_applicable"},
        "liveness": {"status": "passed", "confidence": 99.1},
        "face_match": {"status": "passed", "similarity": 98.2},
        "registry": {"status": "not_applicable", "data_match": None, "face_match": None},
    },
    "amount": 400,
    "created_at": "2026-10-24T20:00:00Z",
    "started_at": "2026-10-24T20:02:10Z",
    "submitted_at": "2026-10-24T20:03:05Z",
    "completed_at": "2026-10-24T20:03:05Z",
    "expires_at": "2026-10-25T20:00:00Z",
}

NEXT_CURSOR = "MjAyNi0xMC0yNFQxODowMDowMFp8aWR2XzNrVDl2UTJtWHc3THAwYUJjRDRlRjZnSA"

VERIFICATION_LIST: dict[str, Any] = {
    "object": "list",
    "data": [VERIFICATION_BIOMETRIC_VERIFIED, VERIFICATION_VERIFIED],
    "has_more": True,
    "next_cursor": NEXT_CURSOR,
}


def verification_page(ids: list[str], *, next_cursor: str | None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{**VERIFICATION_VERIFIED, "id": verification_id} for verification_id in ids],
        "has_more": next_cursor is not None,
        "next_cursor": next_cursor,
    }


def _file(name: str) -> dict[str, Any]:
    return {
        "url": f"https://files.example.com/{VERIFICATION_ID}/{name}.jpg?signature=ejemplo",
        "expires_at": "2026-10-24T18:25:00Z",
    }


VERIFICATION_FILES: dict[str, Any] = {
    "object": "identity.verification_files",
    "front": _file("front"),
    "back": _file("back"),
    "selfie": _file("selfie"),
}

# Los eventos traen la verificación siempre con person en null, también en verified.
EVENT_VERIFICATION_VERIFIED: dict[str, Any] = {
    "id": "evt_7cW2pL9xT4bN6kR1mZ8vH3jQ",
    "object": "event",
    "type": "identity.verification.verified",
    "api_version": "2026-10-23",
    "created_at": "2026-10-24T18:09:58Z",
    "livemode": True,
    "data": {"object": {**VERIFICATION_VERIFIED, "person": None}},
}

EVENT_VERIFICATION_CANCELED: dict[str, Any] = {
    "id": "evt_2nK8fR5yW3cV7qL1pX9dG4sM",
    "object": "event",
    "type": "identity.verification.canceled",
    "api_version": "2026-10-23",
    "created_at": "2026-10-24T18:30:00Z",
    "livemode": True,
    "data": {"object": VERIFICATION_CANCELED},
}
