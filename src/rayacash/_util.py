"""Logging, User-Agent y enmascarado de la clave."""

from __future__ import annotations

import logging
import os
import platform
import sys
from collections.abc import Mapping
from typing import Any

import httpx
from typing_extensions import NotRequired, TypedDict

from rayacash._version import VERSION

logger = logging.getLogger("rayacash")

# Como STRIPE_LOG: se lee una vez, al importar. rayacash.log lo pisa en runtime.
RAYA_LOG = os.environ.get("RAYA_LOG")


class AppInfo(TypedDict):
    """Identifica tu integración o plugin en el User-Agent (lo ves en Developers › Logs)."""

    name: str
    version: NotRequired[str]
    url: NotRequired[str]


def _console_level() -> str | None:
    import rayacash

    level = rayacash.log or RAYA_LOG
    return level if level in ("debug", "info") else None


def _logfmt(props: Mapping[str, Any]) -> str:
    parts = []
    for key, value in props.items():
        text = str(value)
        if not text or any(c in text for c in ' ="\\'):
            text = '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
        parts.append(f"{key}={text}")
    return " ".join(parts)


def log_debug(message: str, **params: Any) -> None:
    line = _logfmt({"message": message, **params})
    if _console_level() == "debug":
        print(line, file=sys.stderr)
    logger.debug(line)


def log_info(message: str, **params: Any) -> None:
    line = _logfmt({"message": message, **params})
    if _console_level() in ("debug", "info"):
        print(line, file=sys.stderr)
    logger.info(line)


def _is_header_safe(text: str) -> bool:
    return all(" " <= c <= "~" for c in text)


def validate_app_info(info: Mapping[str, Any]) -> AppInfo:
    if not isinstance(info, Mapping):
        raise TypeError(
            'app_info tiene que ser un dict como {"name": "mi-plugin", "version": "1.2.0"}.'
        )
    unknown = set(info) - {"name", "version", "url"}
    if unknown:
        raise ValueError(f"app_info no acepta {sorted(unknown)[0]!r}: usá name, version y url.")
    name = info.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("app_info necesita un name.")
    result: AppInfo = {"name": name}
    for field in ("version", "url"):
        value = info.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(f"app_info[{field!r}] tiene que ser un str.")
        result[field] = value
    for value in (result["name"], result.get("version"), result.get("url")):
        if value is not None and not _is_header_safe(value):
            raise ValueError(
                "app_info solo admite caracteres ASCII visibles: va en el header User-Agent."
            )
    return result


def format_app_info(info: AppInfo) -> str:
    text = info["name"]
    version = info.get("version")
    if version:
        text += "/" + version
    url = info.get("url")
    if url:
        text += " (" + url + ")"
    return text


def user_agent(app_info: AppInfo | None) -> str:
    ua = f"rayacash-python/{VERSION} Python/{platform.python_version()} httpx/{httpx.__version__}"
    if app_info:
        ua += " " + format_app_info(app_info)
    return ua


def mask_key(key: str | None) -> str | None:
    """raya_sk_live_…AbCd: para repr y logs. Nunca mostramos la clave entera."""
    if not key:
        return None
    prefix = "raya_sk_live_" if key.startswith("raya_sk_live_") else ""
    if len(key) <= len(prefix) + 8:
        return prefix + "…"
    return f"{prefix}…{key[-4:]}"
