"""Webhooks con Flask: verificá la firma sobre el body crudo antes de procesar.

pip install flask rayacash
RAYA_WEBHOOK_SECRET=whsec_… flask --app examples/webhook_flask.py run
"""

import os

from flask import Flask, request

import rayacash

app = Flask(__name__)
processed_events: set[str] = set()  # en producción, tu base de datos


@app.post("/webhooks/raya")
def raya_webhook() -> tuple[str, int]:
    try:
        event = rayacash.Webhook.construct_event(
            request.get_data(),  # el body crudo: request.get_json() lo re-serializaría
            request.headers.get("Raya-Signature"),
            os.environ["RAYA_WEBHOOK_SECRET"],
        )
    except rayacash.SignatureVerificationError:
        return "Firma inválida", 400

    # El mismo evento puede llegar más de una vez: procesá cada id una sola vez.
    if event.id in processed_events:
        return "", 200
    processed_events.add(event.id)

    if event.type == "payment.succeeded":
        payment = event.data.object
        print(f"Pagaron el pedido {payment['external_reference']}: entregalo.")
    elif event.type == "payment.failed":
        print("Transfirieron de menos: devolvemos el dinero solos. No entregues el pedido.")
    elif event.type == "transfer.received":
        print(f"Depósito de ${event.data.object['net_amount']}")
    # webhook.test y los tipos que no conocés: respondé 2xx e ignoralos.
    return "", 200
