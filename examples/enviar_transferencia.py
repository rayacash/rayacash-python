"""Enviar una transferencia a un CBU, CVU o alias, sin riesgo de mandarla dos veces.

ATENCIÓN: no hay modo de prueba. Correr este script transfiere plata real desde tu saldo.

    RAYA_SECRET_KEY=raya_sk_live_… python examples/enviar_transferencia.py <destino> <monto>
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal

import rayacash


def pay_supplier(client: rayacash.RayaClient, destination: str, amount: Decimal, key: str) -> None:
    try:
        transfer = client.transfers.create(
            amount=amount, destination=destination, idempotency_key=key
        )
    except rayacash.UnprocessableEntityError as error:
        # INSUFFICIENT_BALANCE, LIMIT_EXCEEDED, DESTINATION_*: no se arregla reintentando.
        print(f"No se pudo transferir: {error.message} ({error.code})")
        return
    except (rayacash.APIConnectionError, rayacash.APIError) as error:
        # Sin respuesta o falla de nuestro lado: reintentá más tarde con la MISMA clave.
        print(f"Reintentá más tarde con la clave {error.idempotency_key}: {error.message}")
        return

    print(f"Transferencia {transfer.id}: {transfer.status}")
    print(f"Titular: {transfer.counterparty.name} (CUIT {transfer.counterparty.tax_id})")
    if transfer.status == "pending":
        print("Te avisamos con transfer.sent o transfer.failed (en general, en uno o dos minutos).")


def main() -> None:
    destination, amount = sys.argv[1], Decimal(sys.argv[2])
    # En tu sistema: generá la clave y guardala con el pago al proveedor ANTES de llamar.
    # Si la transferencia termina failed, para intentarla de nuevo usá una clave nueva.
    key = str(uuid.uuid4())
    with rayacash.RayaClient() as client:
        pay_supplier(client, destination, amount, key)


if __name__ == "__main__":
    main()
