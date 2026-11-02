"""Cuándo y cuánto esperar para reintentar. Funciones puras: el requestor las usa en su bucle.

Política (api.md › «Qué hacer según la respuesta»):

- Sin respuesta (corte, timeout): se reintenta. Los POST siempre llevan Idempotency-Key, así
  que nunca se ejecutan dos veces.
- ``409 IDEMPOTENCY_KEY_IN_USE``, ``429``, ``408`` y ``5xx``: se reintenta, esperando el
  ``Retry-After`` si viene. Si pide más de ``MAX_RETRY_AFTER`` (un reembolso puede pedir
  3600 s), no se reintenta: el error sale con ``retry_after`` para que lo reprogrames.
- ``503 API_UNAVAILABLE`` es un interruptor (mantenimiento): no se reintenta.
- Cualquier otro ``4xx``: no se hizo nada; reintentar igual da lo mismo.
"""

from __future__ import annotations

import email.utils
import random
import time
from datetime import timezone

import anyio

INITIAL_DELAY = 0.5
MAX_DELAY = 8.0
MAX_RETRY_AFTER = 60.0


def sleep(seconds: float) -> None:
    time.sleep(seconds)


async def sleep_async(seconds: float) -> None:
    await anyio.sleep(seconds)


def _jitter() -> float:
    return random.random()


def parse_retry_after(value: str | None) -> float | None:
    """Segundos del header Retry-After (también acepta la forma de fecha HTTP)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.isascii() and value.isdigit():
        # float() del texto, nunca de int(): un número que no entra en un float vale inf (no se
        # reintenta), como en Node.js y PHP, en vez de un OverflowError.
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:  # Python < 3.10 devuelve None con algunas fechas inválidas.
        return None  # pragma: no cover
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, when.timestamp() - time.time())


def backoff_delay(retry_number: int) -> float:
    """Espera antes del reintento número ``retry_number`` (1, 2, …): exponencial con jitter."""
    # El exponente va con tope: desde el reintento 1025, 2.0 ** (n - 1) no entra en un float
    # (OverflowError). Con 64 la espera ya pasó MAX_DELAY de largo.
    base = min(INITIAL_DELAY * 2.0 ** min(retry_number - 1, 64), MAX_DELAY)
    return base / 2 + base / 2 * _jitter()


def retry_delay(retry_number: int, retry_after: float | None) -> float:
    delay = backoff_delay(retry_number)
    if retry_after is not None:
        delay = max(delay, retry_after)
    return delay


def should_retry_response(status: int, code: str | None, retry_after: float | None) -> bool:
    if status == 409:
        retryable = code == "IDEMPOTENCY_KEY_IN_USE"
    elif status == 503 and code == "API_UNAVAILABLE":
        retryable = False
    else:
        retryable = status in (408, 429) or status >= 500
    if retryable and retry_after is not None and retry_after > MAX_RETRY_AFTER:
        return False
    return retryable
