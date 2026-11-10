# rayacash

El SDK oficial de Python para la [API de Raya Cash](https://raya.cash/api). Te deja cobrar por transferencia con un CVU exclusivo por pago, mandar plata a cualquier CBU, CVU o alias, consultar tu saldo, conciliar tus depósitos y verificar los webhooks, con reintentos seguros e idempotencia incluidos. Y si construís una app, cobrar a nombre de otras cuentas de Raya con tu comisión ([Raya Connect](#raya-connect)).

```python
import rayacash

client = rayacash.RayaClient()  # lee tu clave secreta de RAYA_SECRET_KEY

payment = client.payments.create(amount=15000, description="Pedido #1042")
print(payment.bank_transfer.cvu, payment.checkout_url)
```

Versión 1.2.0. Requiere Python 3.9 o más nuevo. Los cambios de cada versión están en [CHANGELOG.md](CHANGELOG.md).

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
- [Raya Connect](#raya-connect)
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
5. **Para cobrar a nombre de otras cuentas:** una app en [Developers › Integraciones › Apps](https://raya.cash/dashboard/developers/apps), con su `client_id` y su `client_secret` (`raya_cs_live_…`). Ver [Raya Connect](#raya-connect).

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

Cada respuesta es un objeto del SDK (`Balance`, `Transfer`, `Payment`, `ConnectOrder`, `User`, `OAuthToken`, `Event` o `ListObject`) que también es un `dict`: `payment.status` y `payment["status"]` dan lo mismo, y `json.dumps(payment)` anda. Los valores vienen tal como los manda la API: montos `int` o `float` y fechas en string ISO 8601 (`"2026-10-24T14:00:00Z"`). Si la API suma un campo nuevo, lo ves igual (`payment["campo_nuevo"]`).

Cada objeto trae `last_response`, con el `request_id` (`req_…`) que nos tenés que mandar si escribís a soporte:

```python
print(payment.last_response.request_id)
```

## Estilo global

También podés configurar una clave para todo el proceso y llamar a las clases:

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

Para las apps, también `rayacash.OAuth.token(...)`, `rayacash.User.retrieve(...)` y `rayacash.ConnectOrder.create/retrieve/refund(...)`, con `rayacash.api_key` igual al `access_token` de la cuenta conectada.

Los dos estilos usan el mismo núcleo y se comportan igual. Preferí `RayaClient` si tu proceso usa más de una clave (por ejemplo, un `access_token` por cuenta conectada) o si querés configurar cada cliente por separado. `payment.refund()` usa el cliente del que vino el pago: si lo trajiste con un `RayaClient`, usa ese cliente; si no, la configuración global.

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
| `408`, `500`, `502`, `503`, `504` | Sí | `Retry-After` o exponencial |
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

## Raya Connect

Si construís una plataforma que cobra **a nombre de otras cuentas de Raya** (un marketplace, un sistema de gestión, una pasarela), usá **Raya Connect**: creá una **app** en [Developers › Integraciones › Apps](https://raya.cash/dashboard/developers/apps). Cada cuenta que la conecte te da un `access_token` para cobrar a su nombre con tu **comisión fija** (`fee`) y para leer sus datos. Es el equivalente de las aplicaciones y el `marketplace_fee` de Mercado Pago. El flujo tiene cuatro pasos.

**1. El link de autorización.** Ponelo en tu web, por ejemplo en un botón «Conectar con Raya». Al tocarlo, la cuenta entra a Raya, ve tu app y sus permisos, y autoriza. Raya la redirige a tu `redirect_uri` (una de las registradas en la app, idéntica) con un `code` en la query, que dura 10 minutos y se canjea una sola vez.

```text
https://raya.cash/authorization?client_id=7650337728110670&response_type=code&redirect_uri=https%3A%2F%2Ftienda.example.com%2Fraya%2Fcallback
```

`state` es opcional, pero recomendado: evita que alguien le haga conectar a tu usuario una cuenta que no es la suya (CSRF). No es un valor fijo ni se escribe a mano, y no sirve para pasar datos: viaja en la URL y cualquiera lo puede cambiar. Tu botón apunta a una ruta de tu servidor que, en cada clic, genera uno aleatorio nuevo, lo guarda en la sesión y redirige al link con `&state=<ese valor>`. Raya te lo devuelve tal cual en la `redirect_uri` y ahí comprobás que sea el mismo (paso 2). Con Flask:

```python
import secrets
from urllib.parse import urlencode

from flask import redirect, session


@app.get("/raya/conectar")  # tu botón «Conectar con Raya» apunta acá
def raya_conectar():
    state = secrets.token_urlsafe(32)  # aleatorio y nuevo en cada clic
    session["raya_state"] = state
    params = {
        "client_id": "7650337728110670",
        "response_type": "code",
        "redirect_uri": "https://tienda.example.com/raya/callback",
        "state": state,
    }
    return redirect(f"https://raya.cash/authorization?{urlencode(params)}")
```

**2. Canjeá el `code` por el `access_token`.** Antes, si mandaste `state`, sacalo de la sesión (se usa una sola vez) y comparalo con el que volvió: si no había uno o no coincide, no canjees el `code`. El canje es la única request sin `Authorization`: tu app se identifica con `client_id` y `client_secret`, así que el `RayaClient` puede no tener clave. `grant_type` lo pone el SDK. Guardá `access_token` y `user_id` como guardás tu clave secreta, junto a la cuenta de tu plataforma (la de tu login, nunca la del `state`). El token **no vence**: deja de valer cuando la cuenta desconecta tu app (desde ahí, `ACCESS_TOKEN_REVOKED`) o cuando vuelve a autorizarla (se emite uno nuevo). `expires_in` y `refresh_token` vienen en `None`.

```python
import os

from flask import redirect, request, session

import rayacash

client = rayacash.RayaClient()  # sin clave: oauth.token no la necesita


@app.get("/raya/callback")  # tu redirect_uri
def raya_callback():
    # El state se usa una sola vez: sacalo de la sesión y comparalo con el que volvió.
    expected = session.pop("raya_state", None)
    if not expected or request.args.get("state") != expected:
        return "state inválido", 400  # no salió de tu botón: no canjees el code
    if request.args.get("error") == "access_denied":
        return redirect("/conectar?cancelado=1")  # la cuenta no autorizó
    token = client.oauth.token(
        client_id="7650337728110670",
        client_secret=os.environ["RAYA_CLIENT_SECRET"],  # raya_cs_live_…, solo en tu servidor
        code=request.args["code"],  # el code que llegó a tu redirect_uri
        redirect_uri="https://tienda.example.com/raya/callback",  # la misma del link
    )
    connection.save(user_id=token.user_id, access_token=token.access_token)
    return redirect("/conectar?ok=1")
```

**3. Leé los datos de la cuenta** con un `RayaClient` que use su `access_token` en lugar de tu clave secreta. Solo podés leer las cuentas conectadas a tu app (cualquier otro id da `USER_NOT_FOUND`), y nunca viene la foto del documento ni el número de trámite:

```python
connected = rayacash.RayaClient(connection.access_token)  # raya_at_live_…

user = connected.users.retrieve(connection.user_id)  # o "me"
print(user.full_name, user.identification.type, user.identification.number)  # DNI o CUIT
print(user.email, user.tax_id, user.identity_verified)
```

**4. Creá pagos a su nombre** con `connect.orders` (desde la 1.2.0). `fee` es tu comisión fija en pesos (no un porcentaje), menor que el total. Quien paga transfiere en `checkout_url` (la página de pago, con el nombre y la imagen del comercio conectado) o al CVU de `bank_transfer`. Al acreditarse, `net_amount` (el total menos `fee`) se liquida a la cuenta conectada y `fee` a la tuya, cada una con su plazo de liquidación (y las dos se pueden adelantar). Un reembolso devuelve todo lo recibido y revierte tu comisión.

```python
order = connected.connect.orders.create(
    items=[{"title": "Pedido 1042", "quantity": 1, "unit_price": 45000}],
    fee=500,  # tu comisión: se liquida a tu cuenta
    external_reference="pedido-1042",
    back_urls={
        "success": "https://tienda.example.com/pedidos/1042",
        "failure": "https://tienda.example.com/pedidos/1042/error",
    },
    auto_return="approved",  # al acreditarse, quien paga vuelve solo a back_urls.success
    notification_url="we_3fN8kQ2vX7mB1pR5tZ9cW4yD",  # tu destino de Developers › Webhooks
    metadata={"pedido_id": "1042"},
    idempotency_key=pedido.idempotency_key,  # un UUID v4 guardado con el pedido
)
print(order.checkout_url, order.net_amount)  # 44500 para la cuenta conectada
for item in order["items"]:  # order.items es el método items() de dict
    print(item.title, item.quantity, item.unit_price)

# Consultar el pago (por ejemplo, cuando quien paga vuelve a back_urls.success).
order = connected.connect.orders.retrieve(order.id)
if order.status == "succeeded":
    ...  # entregá el pedido

# Reembolsar (total, hasta 30 días después de pagado): también order.refund().
order = connected.connect.orders.refund(order.id, idempotency_key=refund.idempotency_key)
```

- Te avisamos con los webhooks `connect.order.created`, `connect.order.succeeded`, `connect.order.failed` y `connect.order.refunded` (con el `ConnectOrder` en `event.data.object`): en el destino de `notification_url` si lo mandaste, o en los suscriptos a `connect.order.*`. La cuenta conectada recibe sus `payment.*` de siempre.
- `order.id` es también el id de su `Payment`: la cuenta conectada lo ve con su propia clave en `payments.retrieve()`.
- `expires_in` (de 300 a 864000 segundos) cambia cuánto dura el pago; por defecto, el plazo del comercio conectado. Mientras está `pending` reserva un CVU de ese comercio.
- La cuenta no necesita haber configurado su negocio en Raya: si no lo hizo (`user.merchant` es `None`), el primer pago le crea el comercio con sus datos legales. `CONNECTED_ACCOUNT_NOT_CONFIGURED` queda para el caso raro de una cuenta sin CUIT/CUIL válido (lo resuelve soporte). Si desconectó tu app, `ACCESS_TOKEN_REVOKED`: pedile que vuelva a conectarla.
- Un `RayaClient` por cuenta conectada. Con pocas cuentas, también podés pasar el token por llamada: `client.users.retrieve("me", options={"api_key": connection.access_token})`.

**Probar sin cuentas reales.** En [Developers › Apps › tu app › Test](https://raya.cash/dashboard/developers/apps) tenés una cuenta de prueba para recorrer el flujo entero sin una segunda cuenta de Raya y sin plata real: abrís tu link de autorización, ingresás con ella y, al canjear el `code`, `client.oauth.token(...)` devuelve el `access_token` de prueba de tu app (`raya_at_test_…`, siempre el mismo). Con el SDK funciona igual que uno real: `users.retrieve("me")` devuelve una persona ficticia y `connect.orders.create(...)`, un pago que no se puede pagar (con un CVU y un alias que no existen). Un pago de prueba no manda webhooks: tu endpoint se prueba con «Enviar evento de prueba» (ver [Webhooks](#webhooks)).

`client.oauth` y `client.users` existen desde la 1.1.0, y `client.connect` y `rayacash.ConnectOrder`, desde la 1.2.0. Si venís de la 1.1.0: `client.checkout.orders` y `rayacash.Checkout` siguen andando como alias deprecados (con un `DeprecationWarning`) hasta la 2.0.0; en código nuevo usá los nombres de arriba.

## Errores

Todos los errores heredan de `rayacash.RayaError`. **Decidí con `error.code`** (estable), nunca con `error.message` (texto en castellano para personas, puede cambiar). Si llega un código que el SDK no conoce, la clase sale del código HTTP.

| Clase | HTTP | Códigos | Qué hacer |
|---|---|---|---|
| `InvalidRequestError` | 400, 405, 413 y los demás `4xx` | `PARAMETER_MISSING`, `PARAMETER_INVALID`, `PARAMETER_UNKNOWN`, `INVALID_JSON`, `OAUTH_GRANT_INVALID`… | Corregí la request: `error.param` dice qué parámetro falló. `OAUTH_GRANT_INVALID`: el `code` ya se usó, venció o la `redirect_uri` no coincide. |
| `NotFoundError` (subclase de la anterior) | 404 | `PAYMENT_NOT_FOUND`, `TRANSFER_NOT_FOUND`, `ORDER_NOT_FOUND`, `USER_NOT_FOUND`, `NOT_FOUND` | No existe, no es de tu cuenta o no es de una cuenta conectada a tu app. |
| `AuthenticationError` | 401 | `API_KEY_MISSING`, `API_KEY_INVALID`, `API_KEY_EXPIRED`, `ACCESS_TOKEN_INVALID`, `ACCESS_TOKEN_REVOKED`, `OAUTH_CLIENT_INVALID`… | Revisá la clave secreta o el `access_token`. `ACCESS_TOKEN_REVOKED`: la cuenta desconectó tu app. |
| `PermissionDeniedError` | 403 | `API_KEY_ACCOUNT_LOCKED`, `API_NOT_ENABLED`, `MERCHANT_NOT_CONFIGURED`, `TRANSFERS_BLOCKED`, `CONNECTED_ACCOUNT_LOCKED`, `CONNECTED_ACCOUNT_NOT_CONFIGURED`, `APP_DISABLED` | La cuenta (o la cuenta conectada, o tu app) no puede hacer esto todavía. |
| `IdempotencyError` | 409 | `IDEMPOTENCY_KEY_REUSED`, `IDEMPOTENCY_KEY_IN_USE` | Una clave por operación; si está en uso, reintentá más tarde con la misma. |
| `ConflictError` | 409 | `PAYMENT_NOT_REFUNDABLE` | Mirá `error.data["status"]` y `error.data.get("reason")`. |
| `UnprocessableEntityError` | 422 | `INSUFFICIENT_BALANCE`, `LIMIT_EXCEEDED`, `DESTINATION_NOT_FOUND`, `DESTINATION_INACTIVE`, `DESTINATION_NOT_SUPPORTED`, `REFUND_FAILED` | No se arregla reintentando: mostráselo a la persona. |
| `RateLimitError` | 429 | `RATE_LIMITED` | Esperá `error.retry_after` segundos. |
| `APIError` | 5xx y 408 | `INTERNAL_ERROR`, `BANK_UNAVAILABLE`, `CVU_UNAVAILABLE`, `API_UNAVAILABLE`, `TEMPORARILY_UNAVAILABLE` | Reintentá más tarde, en los POST con la misma `idempotency_key`. |
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

Te avisamos en tu servidor apenas pasa algo: `payment.succeeded` cuando llega la transferencia de un pago, `transfer.received` cuando te depositan, `connect.order.succeeded` cuando se acredita un pago de tu app, etc. **Antes de procesar un evento, verificá la firma**:

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
- `event.data.object` es el `Transfer`, el `Payment` o el `ConnectOrder` tal como estaba cuando ocurrió el evento.
- «Enviar evento de prueba» (en Developers › Webhooks) manda un `webhook.test`: respondé `2xx` e ignoralo.
- La firma tolera 5 minutos de diferencia con tu reloj (`tolerance=300`). Mientras rotás el secreto llegan dos firmas: alcanza con que coincida una.
- Con `client.construct_event(...)` el evento queda ligado a ese cliente: `event.data.object.refund()` usa su clave. Para un `ConnectOrder`, el cliente tiene que llevar el `access_token` de la cuenta conectada.

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

El `http_client` falso prueba tu código sin red; el flujo real de una app (autorizar, canjear el `code` y crear un pago) se prueba con la cuenta de prueba: ver «Probar sin cuentas reales», en [Raya Connect](#raya-connect).

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
- **`app_info`:** identifica tu plugin en el `User-Agent` (`rayacash-python/1.2.0 … mi-plugin/1.2.0`), que ves en [Developers › Logs](https://raya.cash/dashboard/developers/logs). En el estilo global: `rayacash.set_app_info("mi-plugin", version="1.2.0")`.
- **Logging:** el SDK usa el logger `rayacash`. Con `RAYA_LOG=info` (o `rayacash.log = "info"`) ves cada request, su status, su `request_id` y los reintentos en stderr; con `debug`, también la query y la idempotency key. Vale para todo el proceso, también para cada `RayaClient`. Nunca logueamos la clave ni los bodies.
- **Cerrar:** `client.close()` / `await client.aclose()`, o usá `with` / `async with`.
- **Endpoints nuevos:** si la API suma un endpoint antes que el SDK, usá `client.raw_request("get", "/v1/…", params=…, body=…)`: tiene la misma autenticación, reintentos y errores. La query va en `params`, nunca en la ruta.
- **Estilo global:** `rayacash.api_base`, `rayacash.timeout`, `rayacash.max_network_retries`, `rayacash.http_client` y `rayacash.async_http_client`.

## Seguridad

- **La clave secreta va solo en tu servidor**, leída de una variable de entorno. Nunca en el navegador, en una app mobile ni en el repositorio. Lo mismo vale para el `client_secret` de tu app y para los `access_token` de las cuentas conectadas. Para cobrar desde el navegador está [Raya.js](https://raya.cash/raya-js), con la clave pública.
- El SDK rechaza la clave pública (`raya_pk_…`) sin mandar nada, nunca muestra completa la clave ni un `access_token` (`repr(client)` y `str(token)` los enmascaran) y nunca sigue redirects.
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

Raya Cash S.A
