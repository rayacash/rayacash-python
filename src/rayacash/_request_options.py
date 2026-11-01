"""Opciones por request: pisan las del cliente (o las globales) solo en esa llamada."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from typing_extensions import TypedDict


class RequestOptions(TypedDict, total=False):
    """Opciones de una sola request.

    - ``api_key``: otra clave secreta para esta llamada.
    - ``timeout``: segundos por intento (o un ``httpx.Timeout``).
    - ``max_network_retries``: reintentos para esta llamada (``0`` los apaga).
    """

    api_key: str
    timeout: float | httpx.Timeout
    max_network_retries: int


_KEYS = frozenset({"api_key", "timeout", "max_network_retries"})


def validate_options(options: Mapping[str, Any] | None) -> RequestOptions:
    if options is None:
        return {}
    if not isinstance(options, Mapping):
        raise TypeError('options tiene que ser un dict, como {"timeout": 90}.')
    unknown = set(options) - _KEYS
    if unknown:
        raise TypeError(
            f"options no acepta {sorted(unknown)[0]!r}: "
            "las opciones son api_key, timeout y max_network_retries."
        )
    result: RequestOptions = {}
    result.update(options)  # type: ignore[typeddict-item]
    return result
