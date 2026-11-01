"""Webhooks con Django: una vista que verifica la firma sobre ``request.body``.

En urls.py: ``path("webhooks/raya", views.raya_webhook)``. Necesita ``RAYA_WEBHOOK_SECRET``.
"""

import os

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import rayacash


@csrf_exempt  # lo llama Raya, no un navegador: la firma reemplaza al token CSRF
@require_POST
def raya_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = rayacash.Webhook.construct_event(
            request.body,  # los bytes tal como llegaron
            request.headers.get("Raya-Signature"),
            os.environ["RAYA_WEBHOOK_SECRET"],
        )
    except rayacash.SignatureVerificationError:
        return HttpResponseBadRequest("Firma inválida")

    # Guardá event.id en tu base (con un unique) para procesar cada evento una sola vez y,
    # si el proceso es lento, encolalo (Celery…) y respondé enseguida: hay 15 s.
    if event.type == "payment.succeeded":
        payment = event.data.object
        print(f"Pagaron {payment['external_reference']}")
    return HttpResponse(status=200)
