"""Webhooks con FastAPI: ``await request.body()`` da el body crudo.

pip install fastapi uvicorn rayacash
RAYA_WEBHOOK_SECRET=whsec_… uvicorn examples.webhook_fastapi:app
"""

import os

from fastapi import FastAPI, HTTPException, Request, Response

import rayacash

app = FastAPI()
client = rayacash.RayaClient()  # para consultar o reembolsar desde el webhook


@app.post("/webhooks/raya")
async def raya_webhook(request: Request) -> Response:
    try:
        event = client.construct_event(
            await request.body(),
            request.headers.get("Raya-Signature"),
            os.environ["RAYA_WEBHOOK_SECRET"],
        )
    except rayacash.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida") from None

    if event.type == "payment.succeeded":
        # Los eventos pueden llegar desordenados: si necesitás el estado actual, consultalo.
        payment = await client.payments.retrieve_async(event.data.object["id"])
        if payment.status == "succeeded":
            print(f"Entregá el pedido {payment.external_reference}")
    return Response(status_code=200)
