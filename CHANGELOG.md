# Changelog

Los cambios de cada versión de `rayacash` publicada en [PyPI](https://pypi.org/project/rayacash/). Sigue [semver](https://semver.org/lang/es/): mientras la versión sea `0.x`, una versión menor puede traer cambios incompatibles, y los anotamos acá.

## 0.1.0 (sin publicar)

Primera versión.

- `rayacash.RayaClient(api_key=None, *, api_base, timeout, max_network_retries, http_client, async_http_client, app_info)`. Sin `api_key`, lee `RAYA_SECRET_KEY`. Rechaza sin hacer ninguna request la clave pública (`raya_pk_…`), una clave vacía o con espacios, y una `api_base` que no sea `https://` (salvo `http://localhost`). Sirve como context manager (`with` / `async with`), tiene `close()` / `aclose()` y su `repr` enmascara la clave.
- Los 7 endpoints, con kwargs explícitos y su gemelo `*_async`:
  - `client.balance.retrieve()`.
  - `client.transfers.create(amount=, destination=, idempotency_key=)`, con la `idempotency_key` obligatoria.
  - `client.transfers.retrieve(transfer_id)`.
  - `client.transfers.list(direction=, status=, created_gte=, created_lt=, limit=, cursor=)`. Acepta `datetime` con zona o strings ISO 8601, y rechaza un `datetime` sin zona.
  - `client.payments.create(amount=, description=, external_reference=, return_url=, metadata=, idempotency_key=)`.
  - `client.payments.retrieve(payment_id)`.
  - `client.payments.refund(payment_id, idempotency_key=)`.
- Opciones por llamada en `options={"api_key", "timeout", "max_network_retries"}`.
- Estilo global, como stripe-python:
  - `rayacash.api_key` (o `RAYA_SECRET_KEY`), `api_base`, `timeout`, `max_network_retries`, `http_client`, `async_http_client`, `log` y `set_app_info()`.
  - `rayacash.Balance.retrieve()`, `rayacash.Transfer.create/retrieve/list()`, `rayacash.Payment.create/retrieve()`.
  - `rayacash.Payment.refund(payment_id)` y `payment.refund()`. La instancia usa el cliente del que vino el pago.
- Objetos (`Balance`, `Transfer`, `Payment`, `Event`, `ListObject`, `RayaObject`):
  - Son `dict` con acceso por atributo, con los valores tal como los manda la API (montos `int`/`float`, fechas en string ISO). `json.dumps(obj)` anda.
  - Conservan los campos que el SDK todavía no conoce.
  - `metadata` queda como dict común.
  - Cada uno trae `last_response`, con `request_id`, `http_status`, `headers` e `idempotency_key`.
- Montos: `amount` acepta `int`, `float`, `Decimal` o `str` decimal y viaja como número JSON canónico (`Decimal("1500.50")` → `1500.5`). Nunca se redondea: lo que tiene más de 2 decimales lo rechaza la API.
- Idempotencia:
  - En `payments.create` y `refund`, sin clave propia se genera un UUID v4 por llamada.
  - Cada reintento usa la misma clave, que queda en `last_response.idempotency_key` y en `error.idempotency_key`.
  - Se valida que la clave tenga de 1 a 255 caracteres ASCII visibles.
- Reintentos:
  - Se reintentan los cortes de conexión, los timeouts, `409 IDEMPOTENCY_KEY_IN_USE`, `429`, `408` y los `5xx`, con espera exponencial con jitter (0,5 s a 8 s) y respetando `Retry-After`. Por defecto son 2.
  - `503 API_UNAVAILABLE` y los `4xx` no se reintentan.
  - Si `Retry-After` pasa de 60 s, el error sale enseguida con `retry_after`.
- Timeout de 65 s por intento (10 s para conectar): el servidor corta a los 60 s y crear un pago puede tardar ~40 s. Nunca se siguen redirects.
- Paginación: `auto_paging_iter()` sirve para `for` y `async for` y pide cada página siguiente con `cursor` y los mismos filtros y opciones. `next_page()` / `next_page_async()`.
- Errores:
  - Jerarquía con base en `RayaError`: `InvalidRequestError` (con `param`), `NotFoundError`, `AuthenticationError`, `PermissionDeniedError`, `ConflictError`, `IdempotencyError`, `UnprocessableEntityError`, `RateLimitError`, `APIError`, `APIConnectionError` y `SignatureVerificationError`.
  - La clase sale del código HTTP y `code` es el del contrato.
  - Las respuestas sin el objeto `error` (HTML del edge) traen `RATE_LIMITED`, `INTERNAL_ERROR` o `INVALID_RESPONSE`, y los cortes, `NETWORK_ERROR` o `TIMEOUT`.
- Webhooks:
  - `rayacash.Webhook.construct_event(payload, sig_header, secret, tolerance=300)` y `client.construct_event(...)`, que liga el evento al cliente.
  - `WebhookSignature.verify_header`, `compute_signature` y `generate_header`, para tus tests.
  - La firma se verifica sobre el body crudo y acepta varias `v1` (rotación del secreto). La tolerancia es simétrica y vale `None` para desactivarla.
  - Probado con los vectores del contrato.
- `client.raw_request()` / `raw_request_async()` para endpoints que el SDK todavía no tiene.
- `User-Agent: rayacash-python/0.1.0 Python/… httpx/…`, más el `app_info` de tu plugin. Se ve en Developers › Logs.
- Logger `rayacash`: `RAYA_LOG=info|debug` o `rayacash.log` lo muestran en stderr. Nunca se loguean la clave ni los bodies.
- Tipos completos (`py.typed`), chequeados con mypy `--strict` y pyright. Python 3.9 a 3.14.
