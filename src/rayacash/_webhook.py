"""Verificación de la firma de los webhooks (header ``Raya-Signature``).

``Raya-Signature: t=<segundos unix>,v1=<firma>[,v1=<firma>]``, con la firma
``HMAC-SHA256(secreto, f"{t}." + body crudo)`` en hexadecimal. El secreto (``whsec_…``) se usa
entero, como texto UTF-8. Mientras rotás el secreto llegan dos ``v1``: alcanza con que coincida
uno. La firma se calcula sobre los bytes tal como llegaron: si tu framework ya parseó el JSON,
volver a serializarlo cambia el body y la firma no coincide.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import TYPE_CHECKING, Union

from rayacash._error import SignatureVerificationError
from rayacash._event import Event

if TYPE_CHECKING:
    from rayacash._requestor import APIRequestor

#: Diferencia máxima (en segundos) entre ``t`` y tu reloj.
DEFAULT_TOLERANCE = 300

Payload = Union[bytes, bytearray, memoryview, str]

_TIMESTAMP = re.compile(r"[0-9]{1,20}")
_SIGNATURE = re.compile(r"[0-9a-fA-F]{64}")


def _now() -> float:
    return time.time()


def _payload_bytes(payload: Payload) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    raise TypeError(
        "payload tiene que ser el body crudo (bytes o str): en Flask, request.get_data(); "
        "en Django, request.body; en FastAPI, await request.body()."
    )


def _check_secret(secret: object) -> str:
    if not isinstance(secret, str):
        raise TypeError("secret tiene que ser el secreto del destino (whsec_…), un str.")
    if not secret.strip():
        raise ValueError("Falta el secreto del webhook (whsec_…): está en Developers › Webhooks.")
    return secret


def _check_tolerance(tolerance: object) -> float | None:
    if tolerance is None:
        return None
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise TypeError("tolerance tiene que ser un número de segundos o None.")
    if tolerance < 0:
        raise ValueError("tolerance no puede ser negativa.")
    return float(tolerance)


def _parse_header(header: str) -> tuple[int | None, list[str]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "t" and timestamp is None and _TIMESTAMP.fullmatch(value):
            timestamp = int(value)
        elif key == WebhookSignature.EXPECTED_SCHEME and _SIGNATURE.fullmatch(value):
            signatures.append(value.lower())
    return timestamp, signatures


class WebhookSignature:
    EXPECTED_SCHEME = "v1"

    @staticmethod
    def compute_signature(payload: Payload, secret: str, timestamp: int) -> str:
        """La firma ``v1`` (hex) de un body con un ``t`` dado."""
        message = f"{timestamp}.".encode("ascii") + _payload_bytes(payload)
        return hmac.new(_check_secret(secret).encode("utf-8"), message, hashlib.sha256).hexdigest()

    @classmethod
    def verify_header(
        cls,
        payload: Payload,
        header: str | None,
        secret: str,
        tolerance: float | None = DEFAULT_TOLERANCE,
    ) -> bool:
        """Devuelve ``True`` si la firma es válida; si no, levanta ``SignatureVerificationError``.

        :param payload: El body crudo, sin parsear.
        :param header: El valor del header ``Raya-Signature``.
        :param secret: El secreto del destino (``whsec_…``).
        :param tolerance: Segundos de diferencia aceptados entre ``t`` y tu reloj, para los dos
            lados. ``None`` desactiva el chequeo: solo para probar con firmas viejas.
        """
        raw = _payload_bytes(payload)
        _check_secret(secret)
        max_skew = _check_tolerance(tolerance)
        body = raw.decode("utf-8", errors="replace")

        if header is not None and not isinstance(header, str):
            raise TypeError("header tiene que ser el valor del header Raya-Signature, un str.")
        if header is None or not header.strip():
            raise SignatureVerificationError("Falta el header Raya-Signature.", header, body)
        timestamp, signatures = _parse_header(header)
        if timestamp is None:
            raise SignatureVerificationError(
                "No pudimos leer t (el momento del envío) del header Raya-Signature.", header, body
            )
        if not signatures:
            raise SignatureVerificationError(
                "El header Raya-Signature no trae firmas v1.", header, body
            )

        expected = cls.compute_signature(raw, secret, timestamp)
        if not any(hmac.compare_digest(expected, signature) for signature in signatures):
            raise SignatureVerificationError(
                "La firma no coincide: revisá el secreto (whsec_…) y que uses el body crudo, "
                "sin parsear.",
                header,
                body,
            )
        if max_skew and abs(_now() - timestamp) > max_skew:
            raise SignatureVerificationError(
                f"El momento de la firma (t={timestamp}) está a más de {max_skew:g} s de tu reloj. "
                "Si es un reintento, se firma con un t nuevo: revisá la hora del servidor.",
                header,
                body,
            )
        return True

    @classmethod
    def generate_header(cls, payload: Payload, secret: str, *, timestamp: int | None = None) -> str:
        """Un header ``Raya-Signature`` válido, para tus propios tests."""
        if timestamp is None:
            timestamp = int(_now())
        elif isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
            raise ValueError("timestamp tiene que ser un int de segundos unix.")
        signature = cls.compute_signature(payload, secret, timestamp)
        return f"t={timestamp},{cls.EXPECTED_SCHEME}={signature}"


def construct_event(
    payload: Payload,
    sig_header: str | None,
    secret: str,
    tolerance: float | None = DEFAULT_TOLERANCE,
    *,
    requestor: APIRequestor | None = None,
) -> Event:
    WebhookSignature.verify_header(payload, sig_header, secret, tolerance)
    data = json.loads(_payload_bytes(payload))
    if not isinstance(data, dict):
        raise ValueError("El body del webhook no es un objeto JSON.")
    return Event.construct_from(data, requestor=requestor)


class Webhook:
    DEFAULT_TOLERANCE = DEFAULT_TOLERANCE

    @staticmethod
    def construct_event(
        payload: Payload,
        sig_header: str | None,
        secret: str,
        tolerance: float | None = DEFAULT_TOLERANCE,
    ) -> Event:
        """Verifica la firma y devuelve el ``Event``.

        Levanta ``SignatureVerificationError`` si la firma no es válida: respondé 400 y no lo
        proceses. El mismo evento puede llegar más de una vez y desordenado: guardá los
        ``event.id`` que ya procesaste.
        """
        return construct_event(payload, sig_header, secret, tolerance)
