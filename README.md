# rayacash

El SDK oficial de Python para la [API de Raya Cash](https://raya.cash/api). Te deja cobrar por transferencia con un CVU exclusivo por pago, mandar plata a cualquier CBU, CVU o alias, consultar tu saldo, conciliar tus depósitos y verificar los webhooks, con reintentos seguros e idempotencia incluidos.

```python
import rayacash

client = rayacash.RayaClient()  # lee tu clave secreta de RAYA_SECRET_KEY

payment = client.payments.create(amount=15000, description="Pedido #1042")
print(payment.bank_transfer.cvu, payment.checkout_url)
```

Versión 1.0.0. Requiere Python 3.9 o más nuevo. Los cambios de cada versión están en [CHANGELOG.md](CHANGELOG.md).

## Contenido

- [Antes de empezar](#antes-de-empezar)
- [Instalación](#instalación)
- [Inicio rápido](#inicio-rápido)
- [Estilo global](#estilo-global)
- [Async](#async)
- [Montos](#montos)
- [Idempotencia](#idempotencia)
- [Reintentos y timeouts](#reintentos-y-timeouts)
- [Paginación](#paginación)
- [Errores](#errores)
- [Webhooks](#webhooks)
- [Tests de tu integración](#tests-de-tu-integración)
- [Configuración avanzada](#configuración-avanzada)
- [Seguridad](#seguridad)
- [Versionado y compatibilidad](#versionado-y-compatibilidad)
- [Desarrollo](#desarrollo)

## Antes de empezar

1. **Tu cuenta de Raya con la identidad verificada** (si no, `API_KEY_ACCOUNT_LOCKED`) y la API habilitada (si no, `API_NOT_ENABLED`: escribinos a soporte@raya.cash).
2. **Tu clave secreta** (`raya_sk_live_…`), de [Developers › API Keys](https://raya.cash/dashboard/developers/api-keys). La vas a ver completa una sola vez: guardala en una variable de entorno de tu servidor.
3. **Para cobrar:** tu negocio configurado en [Configuración › Negocio](https://raya.cash/dashboard/settings/business). Sin eso, crear un pago da `MERCHANT_NOT_CONFIGURED`.
4. **Para los webhooks:** un destino en [Developers › Webhooks](https://raya.cash/dashboard/developers/webhooks) y su secreto (`whsec_…`).

## Instalación

```bash
pip install rayacash
# o
uv add rayacash
```

La única dependencia es [httpx](https://www.python-httpx.org/) (más `typing_extensions`).

## Inicio rápido

```python
import os
from decimal import Decimal

import rayacash

client = rayacash.RayaClient(os.environ["RAYA_SECRET_KEY"])

# Tu saldo disponible, en pesos.
balance = client.balance.retrieve()
print(balance.available)

# Cobrar: un pago con un CVU y un alias exclusivos.
payment = client.payments.create(
    amount=15000,
    description="Pedido #1042",
    external_reference="pedido-1042",
    return_url="https://tienda.example.com/pedidos/1042",
    metadata={"cliente_id": "8812"},
    idempotency_key=order.payment_idempotency_key,  # un UUID v4 guardado con el pedido
)
# Mostrá payment.bank_transfer.cvu y payment.bank_transfer.alias, o mandá a quien paga a:
print(payment.checkout_url)

# Consultar un pago (por ejemplo, cuando quien paga vuelve a return_url).
payment = client.payments.retrieve(payment.id)
if payment.status == "succeeded":
    ...  # entregá el pedido

# Reembolsar un pago (total, hasta 30 días después de pagado).
payment = client.payments.refund(payment.id, idempotency_key=refund.idempotency_key)

# Enviar una transferencia a un CBU, CVU o alias. La idempotency_key es obligatoria.
transfer = client.transfers.create(
    amount=Decimal("25000.50"),
    destination="0000123380736153041182",
    idempotency_key=payout.idempotency_key,  # guardala ANTES de llamar
)
print(transfer.status, transfer.counterparty.name)  # "pending" (otro banco) o "completed" (Raya)

# Tus depósitos de un día, página por página.
for deposit in client.transfers.list(
    direction="inbound",
    created_gte="2026-10-23T00:00:00-03:00",
    created_lt="2026-10-24T00:00:00-03:00",
    limit=100,
).auto_paging_iter():
    print(deposit.id, deposit.net_amount)
```

Cada respuesta es un objeto del SDK (`Balance`, `Transfer`, `Payment`, `Event` o `ListObject`) que también es un `dict`: `payment.status` y `payment["status"]` dan lo mismo, y `json.dumps(payment)` anda. Los valores vienen tal como los manda la API: montos `int` o `float` y fechas en string ISO 8601 (`"2026-10-24T14:00:00Z"`). Si la API suma un campo nuevo, lo ves igual (`payment["campo_nuevo"]`).

Cada objeto trae `last_response`, con el `request_id` (`req_…`) que nos tenés que mandar si escribís a soporte:

```python
print(payment.last_response.request_id)
```

## Estilo global

Si venís de stripe-python, también podés configurar una clave para todo el proceso y llamar a las clases:

```python
import os

import rayacash

rayacash.api_key = os.environ["RAYA_SECRET_KEY"]  # si no la asignás, se lee de RAYA_SECRET_KEY

balance = rayacash.Balance.retrieve()
payment = rayacash.Payment.create(amount=15000, description="Pedido #1042")
payment = rayacash.Payment.retrieve(payment.id)
refunded = payment.refund()  # o rayacash.Payment.refund(payment.id)
transfer = rayacash.Transfer.create(
    amount=25000, destination="proveedor.ejemplo", idempotency_key=payout.idempotency_key
)
page = rayacash.Transfer.list(direction="inbound")
```

Los dos estilos usan el mismo núcleo y se comportan igual. Preferí `RayaClient` si tu proceso usa más de una clave o si querés configurar cada cliente por separado. `payment.refund()` usa el cliente del que vino el pago: si lo trajiste con un `RayaClient`, usa ese cliente; si no, la configuración global.

## Async

Cada método tiene su versión `*_async`, para asyncio (FastAPI, Starlette, aiohttp…):

```python
import rayacash

client = rayacash.RayaClient()


async def conciliar() -> None:
    balance = await client.balance.retrieve_async()
    payment = await client.payments.create_async(amount=15000)
    page = await client.transfers.list_async(direction="inbound")
    async for transfer in page.auto_paging_iter():
        print(transfer.id)
    await client.aclose()  # o usá `async with rayacash.RayaClient() as client:`
```

## Montos

- La API trabaja en **pesos** (no en centavos), con hasta 2 decimales. `currency` es siempre `"ARS"`.
- **Para mandar** un monto podés pasar `int`, `Decimal`, `float` o un `str` decimal: `15000`, `Decimal("15000.50")`, `15000.5` o `"15000.50"`. Viaja como número JSON (nunca como string).
- **El SDK nunca redondea.** Si mandás más de 2 decimales (por ejemplo, un float con ruido como `0.1 + 0.2`), la API responde `PARAMETER_INVALID` y no se hace nada. Si tus montos salen de cuentas, usá `Decimal` y redondeá vos con `quantize(Decimal("0.01"))`.
- **Los montos que recibís** (`amount`, `fee`, `net_amount`, `available`…) llegan como los manda la API: `int` si son redondos y `float` si tienen centavos. Para sumar o comparar con exactitud (por ejemplo, contra un `DecimalField` de Django), convertilos así:

```python
from decimal import Decimal

total = sum(Decimal(str(t.net_amount)) for t in page)  # exacto: Decimal("48169.59")
```

## Idempotencia

Con una `Idempotency-Key` podés reintentar un POST sin miedo a que se haga dos veces: si ya lo procesamos, te devolvemos el mismo resultado.

- **`transfers.create` exige `idempotency_key`.** Generá un UUID v4 (`str(uuid.uuid4())`) para cada transferencia, **guardalo con la operación en tu base antes de llamar** y reusalo en cada reintento. Así, si tu proceso se corta después de mandar la request, el reintento no transfiere dos veces.
- En `payments.create` y `payments.refund` es opcional pero recomendada. Si no la pasás, el SDK genera una que protege solo los reintentos de esa llamada.
- El SDK reintenta siempre con la misma clave. La que usó queda en `obj.last_response.idempotency_key` y en `error.idempotency_key`, para que puedas reintentar más tarde.
- Guardamos cada clave 24 horas, para toda tu cuenta. Usar la misma clave con otros parámetros da `IdempotencyError` con `code == "IDEMPOTENCY_KEY_REUSED"`.
- Si una transferencia terminó `failed`, para intentarla de nuevo usá una clave **nueva**: con la misma te devolvemos la respuesta original.

```python
import uuid

key = str(uuid.uuid4())
payout.save_idempotency_key(key)  # primero guardala

try:
    transfer = client.transfers.create(
        amount=25000, destination="proveedor.ejemplo", idempotency_key=key
    )
except rayacash.APIConnectionError:
    ...  # no sabemos si salió: reintentá más tarde con la MISMA key (nunca se hace dos veces)
```

## Reintentos y timeouts

El SDK reintenta solo lo que es seguro reintentar, siempre con la misma `Idempotency-Key`:

| Respuesta | ¿Reintenta? | Espera |
|---|---|---|
| Sin respuesta (corte de conexión, timeout) | Sí | Exponencial con jitter (0,5 s, 1 s, 2 s… hasta 8 s) |
| `409 IDEMPOTENCY_KEY_IN_USE` | Sí | Lo que pide `Retry-After` |
| `429 RATE_LIMITED` | Sí | `Retry-After` |
| `500`, `502`, `503`, `504` | Sí | `Retry-After` o exponencial |
| `503 API_UNAVAILABLE` (mantenimiento) | No | — |
| Cualquier otro `4xx` | No: no se hizo nada | — |

- Por defecto, **2 reintentos** (3 intentos en total). Cambialo con `RayaClient(max_network_retries=…)` o por llamada con `options={"max_network_retries": 0}`.
- Si el servidor pide esperar más de 60 s (`Retry-After`), el SDK no se queda esperando: levanta el error con `error.retry_after` para que lo reprogrames.
- **Timeout:** 65 s por intento (10 s para conectar). Crear un pago puede tardar hasta 40 s si damos de alta un CVU nuevo y el servidor corta a los 60 s, así que no lo bajes de 60. Cambialo con `RayaClient(timeout=…)` o por llamada con `options={"timeout": 90}`.

```python
client = rayacash.RayaClient(max_network_retries=4, timeout=90)
balance = client.balance.retrieve(options={"timeout": 10, "max_network_retries": 0})
```

## Paginación

`transfers.list()` devuelve una página (`ListObject`) de la más nueva a la más vieja. Iterarla recorre esa página; `auto_paging_iter()` recorre todas, pidiendo las siguientes con los mismos filtros:

```python
from datetime import datetime, timedelta, timezone

argentina = timezone(timedelta(hours=-3))
page = client.transfers.list(
    direction="inbound",  # o "outbound"
    status="completed",  # pending, completed, failed o reversed
    created_gte=datetime(2026, 10, 1, tzinfo=argentina),  # datetime con zona o string ISO 8601
    created_lt=datetime(2026, 11, 1, tzinfo=argentina),  # rango semiabierto: los meses no se pisan
    limit=100,  # de 1 a 100 (por defecto, 20)
)
for transfer in page.auto_paging_iter():
    print(transfer.id, transfer.amount)

# A mano: page.has_more, page.next_cursor y page.next_page().
```

Los cobros de tus pagos no aparecen en Transferencias: se siguen en cada `Payment` y con los webhooks `payment.*`.

## Errores

Todos los errores heredan de `rayacash.RayaError`. **Decidí con `error.code`** (estable), nunca con `error.message` (texto en castellano para personas, puede cambiar). Si llega un código que el SDK no conoce, la clase sale del código HTTP.

| Clase | HTTP | Códigos | Qué hacer |
|---|---|---|---|
| `InvalidRequestError` | 400, 405, 413 | `PARAMETER_MISSING`, `PARAMETER_INVALID`, `PARAMETER_UNKNOWN`, `INVALID_JSON`… | Corregí la request: `error.param` dice qué parámetro falló. |
| `NotFoundError` (subclase de la anterior) | 404 | `PAYMENT_NOT_FOUND`, `TRANSFER_NOT_FOUND` | No existe o no es de tu cuenta. |
| `AuthenticationError` | 401 | `API_KEY_MISSING`, `API_KEY_INVALID`, `API_KEY_EXPIRED`… | Revisá la clave secreta. |
| `PermissionDeniedError` | 403 | `API_KEY_ACCOUNT_LOCKED`, `API_NOT_ENABLED`, `MERCHANT_NOT_CONFIGURED`, `TRANSFERS_BLOCKED` | La cuenta no puede hacer esto todavía. |
| `IdempotencyError` | 409 | `IDEMPOTENCY_KEY_REUSED`, `IDEMPOTENCY_KEY_IN_USE` | Una clave por operación; si está en uso, reintentá más tarde con la misma. |
| `ConflictError` | 409 | `PAYMENT_NOT_REFUNDABLE` | Mirá `error.data["status"]` y `error.data.get("reason")`. |
| `UnprocessableEntityError` | 422 | `INSUFFICIENT_BALANCE`, `LIMIT_EXCEEDED`, `DESTINATION_NOT_FOUND`, `DESTINATION_INACTIVE`, `DESTINATION_NOT_SUPPORTED`, `REFUND_FAILED` | No se arregla reintentando: mostráselo a la persona. |
| `RateLimitError` | 429 | `RATE_LIMITED` | Esperá `error.retry_after` segundos. |
| `APIError` | 5xx | `INTERNAL_ERROR`, `BANK_UNAVAILABLE`, `CVU_UNAVAILABLE`, `API_UNAVAILABLE`, `TEMPORARILY_UNAVAILABLE` | Reintentá más tarde, en los POST con la misma `idempotency_key`. |
| `APIConnectionError` | — | `NETWORK_ERROR`, `TIMEOUT` | No llegó respuesta: reintentá con la misma `idempotency_key`. |

Cada error trae `code`, `message`, `data`, `http_status`, `request_id`, `idempotency_key`, `retry_after`, `headers` y el body crudo (`http_body`, `json_body`).

```python
try:
    transfer = client.transfers.create(
        amount=25000, destination="proveedor.ejemplo", idempotency_key=key
    )
except rayacash.UnprocessableEntityError as error:
    if error.code == "INSUFFICIENT_BALANCE":
        print("No te alcanza el saldo.")
    else:
        print(error.message)
except rayacash.APIError as error:
    if error.code == "BANK_UNAVAILABLE":
        ...  # no se descontó nada: reintentá más tarde con la misma key
except rayacash.RayaError as error:
    print(f"Falló ({error.code}). Request: {error.request_id}")
```

Un reembolso que la red todavía no confirmó sale como `APIError` con `code == "BANK_UNAVAILABLE"`: el pago sigue `succeeded` y la devolución nunca se manda dos veces. Esperá el webhook `payment.refunded` o reintentá más tarde con la misma clave.

## Webhooks

Te avisamos en tu servidor apenas pasa algo: `payment.succeeded` cuando llega la transferencia de un pago, `transfer.received` cuando te depositan, etc. **Antes de procesar un evento, verificá la firma**:

```python
import os

from flask import Flask, request

import rayacash

app = Flask(__name__)


@app.post("/webhooks/raya")
def raya_webhook():
    try:
        event = rayacash.Webhook.construct_event(
            request.get_data(),  # el body crudo, sin parsear
            request.headers.get("Raya-Signature"),
            os.environ["RAYA_WEBHOOK_SECRET"],  # whsec_…
        )
    except rayacash.SignatureVerificationError:
        return "Firma inválida", 400

    if already_processed(event.id):  # el mismo evento puede llegar más de una vez
        return "", 200

    if event.type == "payment.succeeded":
        payment = event.data.object
        fulfill_order(payment.external_reference)
    elif event.type == "transfer.received":
        record_deposit(event.data.object)

    return "", 200
```

- **Usá el body crudo, tal como llegó.** Si tu framework ya parseó el JSON, volver a serializarlo cambia el body y la firma no coincide. En Flask, `request.get_data()`; en Django, `request.body`; en FastAPI, `await request.body()`. Hay ejemplos completos en [`examples/`](examples).
- Respondé `2xx` en menos de 15 segundos. Si tenés que hacer algo lento, guardá el evento, respondé y procesalo después.
- El mismo evento puede llegar más de una vez y desordenado: guardá los `event.id` que procesaste y, si necesitás el estado actual, consultá el objeto con la API.
- `event.data.object` es el `Transfer` o el `Payment` tal como estaba cuando ocurrió el evento.
- «Enviar evento de prueba» (en Developers › Webhooks) manda un `webhook.test`: respondé `2xx` e ignoralo.
- La firma tolera 5 minutos de diferencia con tu reloj (`tolerance=300`). Mientras rotás el secreto llegan dos firmas: alcanza con que coincida una.
- Con `client.construct_event(...)` el evento queda ligado a ese cliente: `event.data.object.refund()` usa su clave.

## Tests de tu integración

Para probar tu código sin llamar a la API, usá un `http_client` falso de httpx: no sale nada a la red.

```python
import httpx

import rayacash


def handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v1/balance"
    return httpx.Response(200, json={"object": "balance", "available": 1500, "currency": "ARS"})


client = rayacash.RayaClient(
    "raya_sk_live_test",
    http_client=httpx.Client(transport=httpx.MockTransport(handler)),
)
assert client.balance.retrieve().available == 1500
```

Para probar tu endpoint de webhooks, firmá el body con `rayacash.WebhookSignature.generate_header(body, secret)` y mandalo en el header `Raya-Signature`.

## Configuración avanzada

```python
import httpx

import rayacash

client = rayacash.RayaClient(
    api_key="raya_sk_live_…",
    api_base="https://api.raya.cash",  # https:// (o http://localhost para desarrollo)
    timeout=65,  # segundos por intento, o un httpx.Timeout
    max_network_retries=2,
    http_client=httpx.Client(proxy="http://proxy.interno:3128"),  # el tuyo: no lo cerramos
    async_http_client=httpx.AsyncClient(proxy="http://proxy.interno:3128"),
    app_info={"name": "mi-plugin", "version": "1.2.0", "url": "https://plugin.example"},
)
```

- **Proxies y certificados:** pasá tus propios `httpx.Client` / `httpx.AsyncClient`. httpx también respeta `HTTPS_PROXY`.
- **`app_info`:** identifica tu plugin en el `User-Agent` (`rayacash-python/1.0.0 … mi-plugin/1.2.0`), que ves en [Developers › Logs](https://raya.cash/dashboard/developers/logs). En el estilo global: `rayacash.set_app_info("mi-plugin", version="1.2.0")`.
- **Logging:** el SDK usa el logger `rayacash`. Con `RAYA_LOG=info` (o `rayacash.log = "info"`) ves cada request, su status, su `request_id` y los reintentos en stderr; con `debug`, también la query y la idempotency key. Nunca logueamos la clave ni los bodies.
- **Cerrar:** `client.close()` / `await client.aclose()`, o usá `with` / `async with`.
- **Endpoints nuevos:** si la API suma un endpoint antes que el SDK, usá `client.raw_request("get", "/v1/…", params=…, body=…)`: tiene la misma autenticación, reintentos y errores.
- **Estilo global:** `rayacash.api_base`, `rayacash.timeout`, `rayacash.max_network_retries`, `rayacash.http_client` y `rayacash.async_http_client`.

## Seguridad

- **La clave secreta va solo en tu servidor**, leída de una variable de entorno. Nunca en el navegador, en una app mobile ni en el repositorio. Para cobrar desde el navegador está [Raya.js](https://raya.cash/raya-js), con la clave pública.
- El SDK rechaza la clave pública (`raya_pk_…`) sin mandar nada, nunca la muestra completa (`repr(client)` la enmascara) y nunca sigue redirects.
- Si la clave se filtró, rotala en Developers › API Keys con vencimiento «Ahora»: la anterior deja de funcionar al instante.
- Las requests que hacés con la clave secreta quedan 30 días en [Developers › Logs](https://raya.cash/dashboard/developers/logs).

## Versionado y compatibilidad

- [Semver](https://semver.org/lang/es/): los cambios incompatibles solo llegan en una versión mayor (`2.0.0`). Las menores (`1.1.0`) suman cosas sin romper nada y las de parche (`1.0.1`) corrigen errores. Todo queda anotado en el [CHANGELOG](CHANGELOG.md).
- La API puede sumar campos, valores de enums, eventos, códigos de error y endpoints. El SDK los deja pasar: tu código tiene que ignorar lo que no conoce.
- Python 3.9 a 3.14. Viene con tipos (`py.typed`): mypy y pyright conocen cada objeto y sus campos.

## Desarrollo

```bash
uv sync                 # entorno con las dependencias de desarrollo
uv run pytest           # tests (nunca llaman a la API: usan httpx.MockTransport)
uv run ruff check . && uv run ruff format --check .
uv run mypy && uv run pyright
uv build                # wheel y sdist en dist/
```

Para publicar una versión: actualizá `src/rayacash/_version.py` y el CHANGELOG, y creá un release `vX.Y.Z` en GitHub. El workflow `release.yml` corre los tests y publica en PyPI con Trusted Publishing.

---

Referencia de la API: https://raya.cash/api · Soporte: soporte@raya.cash
