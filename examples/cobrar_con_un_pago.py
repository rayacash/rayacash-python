"""Cobrar con un pago: crea un pago y muestra los datos para transferir.

ATENCIÓN: no hay modo de prueba. Correr este script crea un pago real en tu negocio, que
reserva un CVU hasta que vence (24 h, salvo que tu negocio tenga otro plazo).

    RAYA_SECRET_KEY=raya_sk_live_… python examples/cobrar_con_un_pago.py
"""

from __future__ import annotations

import uuid

import rayacash


def main() -> None:
    client = rayacash.RayaClient()  # lee RAYA_SECRET_KEY

    # En tu sistema: generá la clave y guardala con el pedido ANTES de llamar, para que un
    # reintento (incluso después de un corte de tu proceso) no cree otro pago.
    idempotency_key = str(uuid.uuid4())

    payment = client.payments.create(
        amount=15000,
        description="Pedido #1042",
        external_reference="pedido-1042",
        return_url="https://tienda.example.com/pedidos/1042",
        metadata={"cliente_id": "8812"},
        idempotency_key=idempotency_key,
    )

    print(f"Pago {payment.id}: {payment.status}")
    print(f"Transferí ${payment.amount} al CVU {payment.bank_transfer.cvu}")
    if payment.bank_transfer.alias is not None:
        print(f"(alias {payment.bank_transfer.alias})")
    print(f"O pagá en {payment.checkout_url}, antes de {payment.expires_at}")

    # Entregá el pedido cuando llegue el webhook payment.succeeded. Si quien paga vuelve a
    # return_url, consultá el pago: volver no significa que haya pagado.
    payment = client.payments.retrieve(payment.id)
    if payment.status == "succeeded":
        print("¡Pagado! Ya podés entregar el pedido.")


if __name__ == "__main__":
    main()
