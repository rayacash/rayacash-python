"""Reembolsar un pago: devuelve todo lo recibido a la cuenta desde la que se pagó.

ATENCIÓN: correr este script devuelve la plata del pago.

    RAYA_SECRET_KEY=raya_sk_live_… python examples/reembolsar_un_pago.py <payment_id>
"""

from __future__ import annotations

import sys
import uuid

import rayacash


def main() -> None:
    payment_id = sys.argv[1]
    key = str(uuid.uuid4())  # en tu sistema, guardala con el reembolso antes de llamar
    client = rayacash.RayaClient()
    try:
        payment = client.payments.refund(payment_id, idempotency_key=key)
    except rayacash.ConflictError as error:
        # PAYMENT_NOT_REFUNDABLE: data["status"] es el estado actual del pago y, si está
        # succeeded, data["reason"] dice por qué (refund_window_expired, payer_unknown…).
        data = error.data or {}
        print(f"No se puede reembolsar: {data.get('status')} {data.get('reason', '')}")
        return
    except rayacash.APIError as error:
        if error.code == "BANK_UNAVAILABLE":
            # Se está confirmando: nunca se manda dos veces. Esperá payment.refunded.
            print(f"La devolución se está confirmando: reintentá más tarde con la clave {key}.")
            return
        raise

    print(f"Pago {payment.id}: {payment.status} ({payment.refunded_at})")


if __name__ == "__main__":
    main()
