"""Emitir facturas electrónicas de ARCA con el Facturador: crear una, consultarla y listarlas.

Necesita el Facturador configurado en Negocios › Facturador, en el dashboard (si no,
FACTURADOR_NOT_READY). ATENCIÓN: «emitir» emite una factura real en ARCA a tu nombre.

Con RAYA_SECRET_KEY=raya_sk_live_… en el entorno:

    python examples/emitir_facturas.py emitir <dni> <monto>
    python examples/emitir_facturas.py consultar <inv_…>
    python examples/emitir_facturas.py listar
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal

import rayacash

# Lo que dice cada motivo de FACTURADOR_NOT_READY (en error.data["reason"]).
NOT_READY = {
    "not_configured": "Todavía no lo configuraste.",
    "checking": "Estamos verificando tu configuración con ARCA: suele tardar unos segundos.",
    "action_required": "Hay algo para revisar en Negocios › Facturador.",
    "certificate_expired": "Venció tu certificado: cargá uno nuevo.",
    "disabled": "Lo desactivaste: para volver a emitir, configuralo de nuevo.",
}


def issue(client: rayacash.RayaClient, dni: str, amount: Decimal) -> None:
    # En tu sistema: generá la clave, guardala con la venta ANTES de llamar y reusala si
    # reintentás. Así un corte nunca emite dos facturas por la misma venta.
    key = str(uuid.uuid4())
    try:
        invoice = client.invoices.create(dni=dni, amount=amount, idempotency_key=key)
    except rayacash.PermissionDeniedError as error:
        if error.code != "FACTURADOR_NOT_READY":
            raise
        reason = str((error.data or {}).get("reason", ""))
        print(f"El Facturador no está listo ({reason}): {NOT_READY.get(reason, error.message)}")
        return
    except rayacash.InvalidRequestError as error:
        # Por ejemplo, un dni que no tiene de 6 a 8 dígitos (error.param == "dni").
        print(f"No se pudo crear: {error.message} ({error.param})")
        return
    except (rayacash.APIConnectionError, rayacash.APIError) as error:
        # Sin respuesta o falla de nuestro lado: reintentá más tarde con la MISMA clave.
        print(f"Reintentá más tarde con la clave {error.idempotency_key}: {error.message}")
        return

    # 202: la emitimos en segundo plano. El resultado llega con invoice.issued, invoice.rejected
    # o invoice.failed.
    print(f"Factura {invoice.type} {invoice.id}: {invoice.status}")
    print(f"Consultala con: python examples/emitir_facturas.py consultar {invoice.id}")


def show(client: rayacash.RayaClient, invoice_id: str) -> None:
    invoice = client.invoices.retrieve(invoice_id)
    print(f"Factura {invoice.type} {invoice.id}: {invoice.status}")
    if invoice.status == "issued":
        print(f"Comprobante {invoice.point_of_sale:05d}-{invoice.number or 0:08d}")
        print(f"CAE {invoice.cae}, vence el {invoice.cae_expires_on}; fecha {invoice.issued_on}")
        # En una Factura C no hay IVA: vat_amount es None y el neto es el total.
        vat = "sin IVA" if invoice.vat_amount is None else f"IVA {invoice.vat_amount}"
        print(f"Neto {invoice.net_amount}, {vat}, total {invoice.amount}")
    elif invoice.failure_reason is not None:
        # Decidí con code, no con message. arca_messages trae lo que dijo ARCA, tal cual.
        print(f"{invoice.failure_reason.code}: {invoice.failure_reason.message}")
        for message in invoice.arca_messages:
            print(f"  ARCA {message.type} {message.code}: {message.message}")
    else:
        print("Todavía la estamos emitiendo: te avisamos con un webhook invoice.*.")


def list_issued(client: rayacash.RayaClient) -> None:
    for invoice in client.invoices.list(status="issued", limit=100).auto_paging_iter():
        print(invoice.id, invoice.issued_on, invoice.number, invoice.amount)


def main() -> None:
    command, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    with rayacash.RayaClient() as client:
        if command == "emitir":
            issue(client, args[0], Decimal(args[1]))
        elif command == "consultar":
            show(client, args[0])
        elif command == "listar":
            list_issued(client)
        else:
            print(__doc__)


if __name__ == "__main__":
    main()
