from __future__ import annotations

import os
from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx
from typing_extensions import Self, deprecated

from rayacash._balance_service import BalanceService
from rayacash._connect_order_service import ConnectService
from rayacash._deprecated import warn_deprecated
from rayacash._encoding import encode_query
from rayacash._event import Event
from rayacash._identity_verification_service import IdentityService
from rayacash._list_object import ListObject
from rayacash._oauth_service import OAuthService
from rayacash._payment_service import PaymentService
from rayacash._raya_object import RayaObject
from rayacash._request_options import RequestOptions, validate_options
from rayacash._requestor import (
    DEFAULT_API_BASE,
    DEFAULT_MAX_NETWORK_RETRIES,
    DEFAULT_TIMEOUT,
    APIRequestor,
    HTTPClientManager,
    RequestorConfig,
    check_api_key,
    normalize_api_base,
    to_timeout,
    validate_max_network_retries,
)
from rayacash._sandbox_helpers_service import SandboxHelpersService
from rayacash._transfer_service import TransferService
from rayacash._user_service import UserService
from rayacash._util import AppInfo, mask_key, user_agent, validate_app_info
from rayacash._webhook import DEFAULT_TOLERANCE, Payload, construct_event


class _ClientConfig(RequestorConfig):
    def __init__(
        self,
        *,
        api_key: str | None,
        api_base: str,
        timeout: httpx.Timeout,
        max_network_retries: int,
        user_agent: str,
        http: HTTPClientManager,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._timeout = timeout
        self._max_network_retries = max_network_retries
        self._user_agent = user_agent
        self._http = http

    def api_key(self) -> str | None:
        return self._api_key

    def api_base(self) -> str:
        return self._api_base

    def timeout(self) -> httpx.Timeout:
        return self._timeout

    def max_network_retries(self) -> int:
        return self._max_network_retries

    def user_agent(self) -> str:
        return self._user_agent

    def http(self) -> HTTPClientManager:
        return self._http


class RayaClient:
    """Cliente de la API de Raya Cash.

    >>> client = rayacash.RayaClient()  # lee la clave de RAYA_SECRET_KEY
    >>> client.balance.retrieve().available

    La clave secreta va solo en tu servidor, leída de una variable de entorno: nunca en el
    navegador, en una app mobile ni en el repositorio.

    Si construís una app que cobra a nombre de otras cuentas, un ``RayaClient`` con el
    ``access_token`` de la cuenta conectada (``raya_at_live_…``) opera por ella:
    ``client.users`` y ``client.connect.orders``. El resto de la API, incluido
    ``client.connect.payouts``, va con tu clave secreta. ``client.oauth.token()`` no necesita clave.

    Para verificar la identidad de tus clientes (Identidad), ``client.identity.verifications``, con
    tu clave secreta.

    En un sandbox, con su clave secreta de prueba (``raya_sk_test_…``), la misma API crea pagos de
    prueba y ``client.test_helpers.payments.simulate_transfer()`` simula que llegó la
    transferencia, sin mover plata.

    :param api_key: Tu clave secreta (``raya_sk_live_…``) o el access_token de una cuenta
        conectada (``raya_at_live_…``). En un sandbox, sus pares de prueba: la clave secreta de
        prueba (``raya_sk_test_…``) o el access_token de un usuario de prueba
        (``raya_at_test_…``). Si no la pasás, se lee de la variable de entorno
        ``RAYA_SECRET_KEY``.
    :param api_base: Por defecto ``https://api.raya.cash``.
    :param timeout: Segundos por intento (por defecto 65, con 10 para conectar) o un
        ``httpx.Timeout``. El servidor corta a los 60 s y crear un pago puede tardar ~40 s.
    :param max_network_retries: Reintentos ante cortes, 408, 429, 5xx e
        ``IDEMPOTENCY_KEY_IN_USE`` (por defecto 2). Los POST reintentan con la misma
        Idempotency-Key, así que nunca se ejecutan dos veces.
    :param http_client: Un ``httpx.Client`` propio (proxies, certificados…). No lo cerramos.
    :param async_http_client: Lo mismo, para los métodos ``*_async``.
    :param app_info: ``{"name", "version", "url"}`` de tu plugin, para el User-Agent.
    """

    balance: BalanceService
    transfers: TransferService
    payments: PaymentService
    oauth: OAuthService
    users: UserService
    connect: ConnectService
    identity: IdentityService
    test_helpers: SandboxHelpersService

    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_base: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        max_network_retries: int | None = None,
        http_client: httpx.Client | None = None,
        async_http_client: httpx.AsyncClient | None = None,
        app_info: AppInfo | None = None,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("RAYA_SECRET_KEY") or None
        if api_key is not None:
            api_key = check_api_key(api_key)
        if http_client is not None and not isinstance(http_client, httpx.Client):
            raise TypeError("http_client tiene que ser un httpx.Client.")
        if async_http_client is not None and not isinstance(async_http_client, httpx.AsyncClient):
            raise TypeError("async_http_client tiene que ser un httpx.AsyncClient.")

        self._config = _ClientConfig(
            api_key=api_key,
            api_base=normalize_api_base(api_base if api_base is not None else DEFAULT_API_BASE),
            timeout=to_timeout(timeout) if timeout is not None else DEFAULT_TIMEOUT,
            max_network_retries=(
                validate_max_network_retries(max_network_retries)
                if max_network_retries is not None
                else DEFAULT_MAX_NETWORK_RETRIES
            ),
            user_agent=user_agent(validate_app_info(app_info) if app_info is not None else None),
            http=HTTPClientManager(http_client, async_http_client),
        )
        self._requestor = APIRequestor(self._config)
        self.balance = BalanceService(self._requestor)
        self.transfers = TransferService(self._requestor)
        self.payments = PaymentService(self._requestor)
        self.oauth = OAuthService(self._requestor)
        self.users = UserService(self._requestor)
        self.connect = ConnectService(self._requestor)
        self.identity = IdentityService(self._requestor)
        self.test_helpers = SandboxHelpersService(self._requestor)

    @property
    # category=None: estos @deprecated son para los type checkers; el DeprecationWarning, con el
    # mismo texto, lo emite warn_deprecated.
    @deprecated(
        "client.checkout está deprecado desde la 1.2.0 y se va en la 2.0.0: usá client.connect.",
        category=None,
    )
    def checkout(self) -> ConnectService:
        """``client.connect`` con su nombre de la 1.1.0: deprecado, se va en la 2.0.0.

        Es el mismo objeto que ``client.connect``: ``client.checkout.orders`` llama a
        ``/v1/connect/orders``. Cada uso (leerlo, asignarlo o borrarlo) avisa con un
        ``DeprecationWarning``.

        Como en la 1.1.0, donde era un atributo común, se puede reemplazar en una instancia
        (``client.checkout = fake``, ``mock.patch.object(client, "checkout")``,
        ``monkeypatch.setattr``): el reemplazo es solo de ``client.checkout`` y va a
        ``vars(client)``, de donde ``mock`` lo restaura. ``del client.checkout``, o asignarle
        ``client.connect``, lo saca: vuelve a ser ``client.connect``.
        """
        warn_deprecated("client.checkout", "client.connect")
        service: ConnectService = self.__dict__.get("checkout", self.connect)
        return service

    @checkout.setter
    @deprecated(
        "client.checkout está deprecado desde la 1.2.0 y se va en la 2.0.0: usá client.connect.",
        category=None,
    )
    def checkout(self, value: ConnectService) -> None:
        warn_deprecated("client.checkout", "client.connect")
        if value is self.connect:
            self.__dict__.pop("checkout", None)
        else:
            self.__dict__["checkout"] = value

    @checkout.deleter
    @deprecated(
        "client.checkout está deprecado desde la 1.2.0 y se va en la 2.0.0: usá client.connect.",
        category=None,
    )
    def checkout(self) -> None:
        warn_deprecated("client.checkout", "client.connect")
        self.__dict__.pop("checkout", None)

    def raw_request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> RayaObject:
        """Una request a cualquier ruta, con la misma autenticación, reintentos y errores.

        Para endpoints que el SDK todavía no tiene: ``client.raw_request("get", "/v1/…")``.
        ``params`` va en la query y ``body`` en el JSON del POST.
        """
        query = encode_query(params) if params else None
        result = self._requestor.request(
            method, path, query=query, body=body, idempotency_key=idempotency_key, options=options
        )
        return self._with_paging(result, method, path, query, options)

    async def raw_request_async(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        options: RequestOptions | None = None,
    ) -> RayaObject:
        """Como ``raw_request()``, para asyncio."""
        query = encode_query(params) if params else None
        result = await self._requestor.request_async(
            method, path, query=query, body=body, idempotency_key=idempotency_key, options=options
        )
        return self._with_paging(result, method, path, query, options)

    @staticmethod
    def _with_paging(
        result: RayaObject,
        method: str,
        path: str,
        query: Mapping[str, str] | None,
        options: RequestOptions | None,
    ) -> RayaObject:
        if isinstance(result, ListObject) and method.upper() == "GET":
            result._set_retrieve_context(path, dict(query or {}), validate_options(options))
        return result

    def construct_event(
        self,
        payload: Payload,
        sig_header: str | None,
        secret: str,
        tolerance: float | None = DEFAULT_TOLERANCE,
    ) -> Event:
        """Como ``rayacash.Webhook.construct_event``, con el evento ligado a este cliente.

        Así, ``event.data.object.refund()`` (o ``.cancel()``, en una ``IdentityVerification``) usa
        la clave de este cliente.
        """
        return construct_event(payload, sig_header, secret, tolerance, requestor=self._requestor)

    def close(self) -> None:
        """Cierra el cliente httpx propio (el que pasaste en ``http_client`` no se toca)."""
        self._config.http().close()

    async def aclose(self) -> None:
        """Cierra los clientes httpx propios, también el async."""
        await self._config.http().aclose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return (
            f"<RayaClient api_base={self._config.api_base()!r} "
            f"api_key={mask_key(self._config.api_key())!r}>"
        )
