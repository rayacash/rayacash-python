"""Cómo viajan los parámetros: JSON con montos exactos, query de las listas e ids en la ruta.

La API parsea los montos como números exactos y rechaza los que tienen más de 2 decimales
(``PARAMETER_INVALID``). Por eso un ``Decimal`` viaja como número JSON, nunca como string, y
el SDK no redondea nunca: si un float trae ruido (``0.1 + 0.2``), lo responde el servidor.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Union
from urllib.parse import quote

#: Un monto en pesos: ``1500``, ``1500.5``, ``Decimal("1500.50")`` o ``"1500.50"``.
Amount = Union[int, float, Decimal, str]

_IDEMPOTENCY_KEY = re.compile(r"[\x21-\x7e]{1,255}")


def canonical_amount(value: object, name: str = "amount") -> Decimal:
    """El monto como ``Decimal`` exacto, sin redondear. El rango lo valida la API."""
    if isinstance(value, bool):
        raise TypeError(
            f"{name} no puede ser un bool: mandá un número en pesos, como 1500 o 1500.5."
        )
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} tiene que ser un número finito, no {value!r}.")
        # repr da el decimal más corto que representa el float: 1500.1 -> "1500.1".
        return Decimal(repr(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} tiene que ser un número finito, no {value!r}.")
        return value
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation:
            raise ValueError(
                f'{name} {value!r} no es un número: usá punto decimal y nada más, como "1500.50".'
            ) from None
        if not parsed.is_finite():
            raise ValueError(f"{name} tiene que ser un número finito, no {value!r}.")
        return parsed
    raise TypeError(
        f"{name} tiene que ser un número en pesos (int, float, Decimal o str decimal), "
        f"no {type(value).__name__}."
    )


def format_decimal(value: Decimal) -> str:
    """El número JSON canónico: Decimal("1500.50") -> 1500.5, Decimal("1E+3") -> 1000."""
    if not value.is_finite():
        raise ValueError(f"No se puede mandar {value!r} en JSON.")
    return format(value.normalize(), "f")


def dumps(value: Any) -> str:
    """JSON compacto en ASCII, con los ``Decimal`` como números (json.dumps no los acepta)."""
    out: list[str] = []
    _encode(value, out)
    return "".join(out)


def _encode(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(json.dumps(value))
    elif isinstance(value, int):
        out.append(int.__repr__(value))
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"No se puede mandar {value!r} en JSON.")
        out.append(float.__repr__(value))
    elif isinstance(value, Decimal):
        out.append(format_decimal(value))
    elif isinstance(value, Mapping):
        out.append("{")
        for index, (key, item) in enumerate(value.items()):
            if not isinstance(key, str):
                raise TypeError(f"Las claves de un objeto JSON tienen que ser str, no {key!r}.")
            if index:
                out.append(",")
            out.append(json.dumps(key))
            out.append(":")
            _encode(item, out)
        out.append("}")
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _encode(item, out)
        out.append("]")
    else:
        raise TypeError(f"No se puede mandar un {type(value).__name__} en JSON.")


def encode_body(params: Mapping[str, Any]) -> bytes:
    """El body de un POST: solo los parámetros que vinieron (la API rechaza los desconocidos)."""
    return dumps({key: value for key, value in params.items() if value is not None}).encode("ascii")


def format_datetime(name: str, value: datetime) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(
            f"{name} necesita zona horaria: usá un datetime con tzinfo (por ejemplo, "
            'timezone.utc) o un string ISO 8601 con zona, como "2026-10-01T00:00:00-03:00".'
        )
    return value.isoformat()


def encode_query(params: Mapping[str, Any]) -> dict[str, str]:
    """La query de una lista: solo los filtros que vinieron."""
    query: dict[str, str] = {}
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            raise TypeError(f"{name} no puede ser un bool.")
        if isinstance(value, datetime):
            query[name] = format_datetime(name, value)
        elif isinstance(value, (int, str)):
            query[name] = str(value)
        else:
            raise TypeError(f"{name} no acepta un {type(value).__name__}.")
    return query


def path_id(name: str, value: object) -> str:
    """Un id para la ruta, codificado: nunca deja una barra final ni un segmento vacío."""
    if not isinstance(value, str):
        raise TypeError(f"{name} tiene que ser un str, no {type(value).__name__}.")
    if not value.strip():
        raise ValueError(f"{name} no puede estar vacío.")
    return quote(value, safe="")


def validate_idempotency_key(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(
            "idempotency_key tiene que ser un str: generá un UUID v4 con str(uuid.uuid4()) "
            "y guardalo junto a la operación antes de llamar."
        )
    if not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ValueError(
            "idempotency_key tiene que tener de 1 a 255 caracteres ASCII visibles, sin espacios "
            "(por ejemplo, un UUID v4)."
        )
    return value
