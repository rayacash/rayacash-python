"""El núcleo de cada request: headers, encoding, reintentos, errores e hidratación.

Lo comparten ``RayaClient`` y el estilo global: cada uno le pasa su configuración.
"""

from __future__ import annotations

import asyncio
import json
import math
import threading
import time
import uuid
import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from rayacash import _retry
from rayacash._encoding import encode_body, validate_idempotency_key
from rayacash._error import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    RayaError,
    error_from_response,
)
from rayacash._list_object import ListObject
from rayacash._raya_object import RayaObject, convert_to_raya_object
from rayacash._request_options import RequestOptions, validate_options
from rayacash._response import RayaResponse
from rayacash._util import log_debug, log_info

DEFAULT_API_BASE = "https://api.raya.cash"
# El servidor corta a los 60 s y crear un pago puede tardar ~40 s: con 65 s por intento
# recibimos la respuesta del servidor en vez de cortar nosotros justo antes.
DEFAULT_TIMEOUT = httpx.Timeout(65.0, connect=10.0)
DEFAULT_MAX_NETWORK_RETRIES = 2

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def check_api_key(key: object) -> str:
    """Rechaza antes de mandar nada lo que nunca puede andar. El formato lo valida la API."""
    if not isinstance(key, str):
        raise TypeError(f"La clave secreta tiene que ser un str, no {type(key).__name__}.")
    if not key.strip():
        raise AuthenticationError(
            "Falta la clave secreta: pasala a RayaClient(api_key=…), asignala a rayacash.api_key "
            "o definí la variable de entorno RAYA_SECRET_KEY.",
            code="API_KEY_MISSING",
        )
    if key.startswith("raya_pk_"):
        raise AuthenticationError(
            "Usaste la clave pública (raya_pk_…). La API se usa con la clave secreta "
            "(raya_sk_live_…), solo desde tu servidor.",
            code="API_KEY_PUBLISHABLE_NOT_ALLOWED",
        )
    if not all("!" <= c <= "~" for c in key):
        raise AuthenticationError(
            "La clave secreta tiene espacios o caracteres inválidos: copiala de nuevo desde "
            "Developers › API Keys.",
            code="API_KEY_INVALID",
        )
    return key


def normalize_api_base(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"api_base tiene que ser un str, no {type(value).__name__}.")
    url = value.strip()
    parts = urlsplit(url)
    secure = parts.scheme == "https" and bool(parts.hostname)
    local = parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS
    if not (secure or local) or parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError(
            "api_base tiene que ser una URL https:// sin query ni credenciales "
            "(o http://localhost para desarrollo local)."
        )
    # Una query o un fragmento vacíos ("https://x?", "https://x#") cuentan como ausentes: se
    # sacan, porque si no las requests irían a https://x/?/v1/… o a https://x/.
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/")


def to_timeout(value: object) -> httpx.Timeout:
    if isinstance(value, httpx.Timeout):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout tiene que ser un número de segundos o un httpx.Timeout.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout tiene que ser un número de segundos mayor que 0.")
    return httpx.Timeout(float(value), connect=min(10.0, float(value)))


def validate_max_network_retries(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("max_network_retries tiene que ser un int.")
    if value < 0:
        raise ValueError("max_network_retries no puede ser negativo.")
    return value


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover - trio u otro runtime
        return None


class HTTPClientManager:
    """Crea los clientes httpx propios cuando hacen falta. Los que pasa el usuario no se tocan."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        async_http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._user_sync = http_client
        self._user_async = async_http_client
        self._owned_sync: httpx.Client | None = None
        self._owned_async: httpx.AsyncClient | None = None
        self._owned_async_loop: weakref.ReferenceType[asyncio.AbstractEventLoop] | None = None
        self._lock = threading.Lock()

    def _new_sync_client(self) -> httpx.Client:
        return httpx.Client(follow_redirects=False)

    def _new_async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(follow_redirects=False)

    def sync_client(self) -> httpx.Client:
        if self._user_sync is not None:
            return self._user_sync
        with self._lock:
            if self._owned_sync is None:
                self._owned_sync = self._new_sync_client()
            return self._owned_sync

    def async_client(self) -> httpx.AsyncClient:
        if self._user_async is not None:
            return self._user_async
        loop = _running_loop()
        with self._lock:
            # Un AsyncClient queda atado al event loop donde se usó: si cambió (dos
            # asyncio.run seguidos), creamos otro.
            previous = self._owned_async_loop() if self._owned_async_loop is not None else None
            if self._owned_async is None or (loop is not None and previous is not loop):
                self._owned_async = self._new_async_client()
                self._owned_async_loop = weakref.ref(loop) if loop is not None else None
            return self._owned_async

    def close(self) -> None:
        with self._lock:
            client, self._owned_sync = self._owned_sync, None
        if client is not None:
            client.close()

    async def aclose(self) -> None:
        with self._lock:
            client, self._owned_async = self._owned_async, None
            self._owned_async_loop = None
        if client is not None:
            await client.aclose()
        self.close()


class RequestorConfig:
    """Lo que el requestor le pregunta a su dueño (RayaClient o el estilo global)."""

    def api_key(self) -> str | None:
        raise NotImplementedError

    def api_base(self) -> str:
        raise NotImplementedError

    def timeout(self) -> httpx.Timeout:
        raise NotImplementedError

    def max_network_retries(self) -> int:
        raise NotImplementedError

    def user_agent(self) -> str:
        raise NotImplementedError

    def http(self) -> HTTPClientManager:
        raise NotImplementedError


@dataclass(frozen=True)
class _Prepared:
    method: str
    path: str
    url: str
    query: dict[str, str]
    headers: dict[str, str]
    content: bytes | None
    timeout: httpx.Timeout
    max_retries: int
    idempotency_key: str | None


_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    httpx.ProxyError,
)


class APIRequestor:
    def __init__(self, config: RequestorConfig) -> None:
        self._config = config

    # --- API pública del requestor -------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
        expected: type[RayaObject] | None = None,
    ) -> RayaObject:
        prepared = self._prepare(method, path, query, body, idempotency_key, options)
        response = self._send(prepared)
        return self._hydrate(prepared, response, expected)

    async def request_async(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
        expected: type[RayaObject] | None = None,
    ) -> RayaObject:
        prepared = self._prepare(method, path, query, body, idempotency_key, options)
        response = await self._send_async(prepared)
        return self._hydrate(prepared, response, expected)

    def request_list(
        self, path: str, *, query: Mapping[str, str], options: RequestOptions | None = None
    ) -> ListObject[Any]:
        page = self.request("GET", path, query=query, options=options, expected=ListObject)
        return self._as_list(page, path, query, options)

    async def request_list_async(
        self, path: str, *, query: Mapping[str, str], options: RequestOptions | None = None
    ) -> ListObject[Any]:
        page = await self.request_async(
            "GET", path, query=query, options=options, expected=ListObject
        )
        return self._as_list(page, path, query, options)

    # --- Preparación ---------------------------------------------------------------------

    def _prepare(
        self,
        method: str,
        path: str,
        query: Mapping[str, str] | None,
        body: Mapping[str, Any] | None,
        idempotency_key: str | None,
        options: RequestOptions | None,
    ) -> _Prepared:
        opts = validate_options(options)
        method = method.upper()
        if method not in ("GET", "POST"):
            raise ValueError("La API solo acepta GET y POST.")
        if not path.startswith("/"):
            raise ValueError("La ruta tiene que empezar con /, como /v1/balance.")
        if "?" in path or "#" in path:
            # httpx reemplaza la query de la ruta por params (y la de cada página siguiente).
            raise ValueError("La ruta va sin query (usá params).")
        if any(c == "\\" or c < " " or c == "\x7f" for c in path):
            # Como en Node.js y PHP: fetch convierte \ en / y saca los saltos y los tabs (httpx
            # los rechaza con InvalidURL, que no es un ValueError).
            raise ValueError("La ruta va sin \\ ni caracteres de control (codificá los ids).")

        api_key = opts.get("api_key")
        if api_key is None:
            api_key = self._config.api_key()
        # Sin clave levanta API_KEY_MISSING antes de cualquier I/O.
        api_key = check_api_key(api_key if api_key is not None else "")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": self._config.user_agent(),
        }
        content = None
        if body is not None:
            content = encode_body(body)
            headers["Content-Type"] = "application/json"

        key: str | None = None
        if method == "POST":
            # Una sola clave por llamada, la misma en cada reintento: nunca se ejecuta dos veces.
            key = (
                validate_idempotency_key(idempotency_key)
                if idempotency_key is not None
                else str(uuid.uuid4())
            )
            headers["Idempotency-Key"] = key
        elif idempotency_key is not None:
            raise ValueError("La Idempotency-Key solo va en los POST.")

        timeout = to_timeout(opts["timeout"]) if "timeout" in opts else self._config.timeout()
        if "max_network_retries" in opts:
            max_retries = validate_max_network_retries(opts["max_network_retries"])
        else:
            max_retries = self._config.max_network_retries()

        return _Prepared(
            method=method,
            path=path,
            url=self._config.api_base() + path,
            query=dict(query or {}),
            headers=headers,
            content=content,
            timeout=timeout,
            max_retries=max_retries,
            idempotency_key=key,
        )

    # --- Envío con reintentos ------------------------------------------------------------

    def _send(self, p: _Prepared) -> httpx.Response:
        client = self._config.http().sync_client()
        retry = 0
        while True:
            self._log_request(p, retry)
            started = time.monotonic()
            try:
                request = client.build_request(
                    p.method,
                    p.url,
                    params=p.query or None,
                    headers=p.headers,
                    content=p.content,
                    timeout=p.timeout,
                )
                response = client.send(request, follow_redirects=False)
            except httpx.RequestError as exc:
                error = self._connection_error(p, exc)
                if not error.should_retry or retry >= p.max_retries:
                    raise error from exc
                retry += 1
                delay = _retry.backoff_delay(retry)
                self._log_retry(p, retry, error.code, delay)
                _retry.sleep(delay)
                continue
            outcome = self._check(p, response, started)
            if outcome is None:
                return response
            if retry >= p.max_retries or not self._should_retry(outcome):
                raise outcome
            retry += 1
            delay = _retry.retry_delay(retry, outcome.retry_after)
            self._log_retry(p, retry, outcome.code, delay)
            _retry.sleep(delay)

    async def _send_async(self, p: _Prepared) -> httpx.Response:
        client = self._config.http().async_client()
        retry = 0
        while True:
            self._log_request(p, retry)
            started = time.monotonic()
            try:
                request = client.build_request(
                    p.method,
                    p.url,
                    params=p.query or None,
                    headers=p.headers,
                    content=p.content,
                    timeout=p.timeout,
                )
                response = await client.send(request, follow_redirects=False)
            except httpx.RequestError as exc:
                error = self._connection_error(p, exc)
                if not error.should_retry or retry >= p.max_retries:
                    raise error from exc
                retry += 1
                delay = _retry.backoff_delay(retry)
                self._log_retry(p, retry, error.code, delay)
                await _retry.sleep_async(delay)
                continue
            outcome = self._check(p, response, started)
            if outcome is None:
                return response
            if retry >= p.max_retries or not self._should_retry(outcome):
                raise outcome
            retry += 1
            delay = _retry.retry_delay(retry, outcome.retry_after)
            self._log_retry(p, retry, outcome.code, delay)
            await _retry.sleep_async(delay)

    @staticmethod
    def _should_retry(error: RayaError) -> bool:
        assert error.http_status is not None
        return _retry.should_retry_response(error.http_status, error.code, error.retry_after)

    def _check(self, p: _Prepared, response: httpx.Response, started: float) -> RayaError | None:
        """None si salió bien (2xx); si no, el error que corresponde."""
        log_info(
            "Respuesta de la API de Raya",
            method=p.method,
            path=p.path,
            status=response.status_code,
            request_id=response.headers.get("raya-request-id", ""),
            elapsed=f"{time.monotonic() - started:.3f}s",
        )
        if response.is_success:
            return None
        return error_from_response(
            http_status=response.status_code,
            headers=response.headers,
            body=response.text,
            idempotency_key=p.idempotency_key,
        )

    @staticmethod
    def _connection_error(p: _Prepared, exc: httpx.RequestError) -> APIConnectionError:
        retryable = isinstance(exc, _RETRYABLE_TRANSPORT_ERRORS)
        if isinstance(exc, httpx.TimeoutException):
            code, message = "TIMEOUT", "La API de Raya no respondió a tiempo."
        else:
            code, message = (
                "NETWORK_ERROR",
                f"No pudimos conectarnos con la API de Raya ({type(exc).__name__}).",
            )
        if p.method == "POST":
            message += " Reintentá con la misma Idempotency-Key: nunca se ejecuta dos veces."
        return APIConnectionError(
            message, code=code, should_retry=retryable, idempotency_key=p.idempotency_key
        )

    @staticmethod
    def _log_request(p: _Prepared, retry: int) -> None:
        log_info("Request a la API de Raya", method=p.method, path=p.path, attempt=retry + 1)
        if p.query or p.idempotency_key:
            log_debug(
                "Detalle de la request",
                query="&".join(f"{k}={v}" for k, v in p.query.items()),
                idempotency_key=p.idempotency_key or "",
            )

    @staticmethod
    def _log_retry(p: _Prepared, retry: int, reason: str | None, delay: float) -> None:
        log_info(
            "Reintentando la request",
            method=p.method,
            path=p.path,
            retry=retry,
            reason=reason or "",
            delay=f"{delay:.2f}s",
        )

    # --- Respuesta -----------------------------------------------------------------------

    def _hydrate(
        self, p: _Prepared, response: httpx.Response, expected: type[RayaObject] | None
    ) -> RayaObject:
        body = response.text
        try:
            # UTF-8 estricto, como Node.js y PHP: el json() de httpx (json.loads() de los bytes)
            # también acepta UTF-16, UTF-32 y los surrogates codificados. "utf-8-sig" deja pasar
            # un BOM, como siempre. UnicodeDecodeError es un ValueError.
            data = json.loads(response.content.decode("utf-8-sig"))
            obj = convert_to_raya_object(data, self, expected) if isinstance(data, dict) else None
        except (ValueError, RecursionError):
            # RecursionError: más niveles de los que Python puede recorrer, al leer el JSON o al
            # armar el objeto.
            data = obj = None
        if not isinstance(obj, RayaObject):
            raise APIError(
                f"La API respondió {response.status_code} con un body que no es un objeto JSON.",
                code="INVALID_RESPONSE",
                http_status=response.status_code,
                request_id=response.headers.get("raya-request-id"),
                headers=response.headers,
                http_body=body,
                idempotency_key=p.idempotency_key,
            )
        last_response = RayaResponse(
            http_status=response.status_code,
            headers=response.headers,
            body=body,
            data=data,
            idempotency_key=p.idempotency_key,
        )
        object.__setattr__(obj, "_last_response", last_response)
        return obj

    @staticmethod
    def _as_list(
        page: RayaObject, path: str, query: Mapping[str, str], options: RequestOptions | None
    ) -> ListObject[Any]:
        if not isinstance(page, ListObject):
            # Con la respuesta, como todo error de la API: request() siempre la deja en el objeto.
            response = page.last_response
            assert response is not None
            raise APIError(
                "La API respondió algo que no es una lista.",
                code="INVALID_RESPONSE",
                http_status=response.http_status,
                request_id=response.request_id,
                headers=response.headers,
                http_body=response.body,
                idempotency_key=response.idempotency_key,
            )
        page._set_retrieve_context(path, dict(query), validate_options(options))
        return page
