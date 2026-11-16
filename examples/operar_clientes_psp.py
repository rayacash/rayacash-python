"""Operar clientes de Raya PSP: crear uno, leer su saldo, transferir en su nombre, bloquearlo y
listarlos.

Necesita una cuenta de empresa con Raya PSP activado (si no, PSP_NOT_ACTIVATED). ATENCIÓN:
«transferir» mueve plata real del saldo de tu cliente (y la comisión, del tuyo).

Con RAYA_SECRET_KEY=raya_sk_live_… en el entorno:

    python examples/operar_clientes_psp.py crear <idv_…>
    python examples/operar_clientes_psp.py saldo <pspc_…>
    python examples/operar_clientes_psp.py transferir <pspc_…> <destino> <monto>
    python examples/operar_clientes_psp.py bloquear <pspc_…>
    python examples/operar_clientes_psp.py listar
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal

import rayacash


def create(client: rayacash.RayaClient, verification_id: str) -> None:
    # En tu sistema: generá la clave, guardala con tu cliente ANTES de llamar y reusala si
    # reintentás. Así un corte nunca crea dos clientes.
    key = str(uuid.uuid4())
    try:
        # Con Identidad alcanza la verificación (document, ya verified): su CUIL, su nombre y su
        # sexo salen de ahí. No mandes tax_id, name, person_type ni fotos con ella.
        customer = client.psp.customers.create(
            identity_verification=verification_id, idempotency_key=key
        )
    except rayacash.ConflictError as error:
        # CUSTOMER_ALREADY_EXISTS: ya tenés un cliente con ese CUIL o ya usaste esa verificación
        # para otro; su id está en error.data.
        print(f"Ya existe: {error.data}")
        return
    except rayacash.InvalidRequestError as error:
        # La verificación no es una document verified de tu cuenta, no tiene un CUIL válido (creá
        # el cliente con sus datos y las fotos) o es de la persona titular de tu cuenta.
        print(f"No se pudo crear: {error.message} ({error.param})")
        return

    print(f"Cliente {customer.id}: {customer.status}")
    if customer.status == "active" and customer.cvu is not None:
        print(f"CVU {customer.cvu.account}, alias {customer.cvu.alias}")
    else:
        # 202: te avisamos con psp.customer.activated, psp.customer.failed o psp.customer.rejected.
        print("Te avisamos el resultado con un webhook psp.customer.*.")


def show_balance(client: rayacash.RayaClient, customer_id: str) -> None:
    customer = client.psp.customers.retrieve(customer_id)
    balance = client.psp.customers.retrieve_balance(customer_id)
    totals = client.psp.balance.retrieve()
    print(f"{customer.name} ({customer.status}): saldo {balance.available}")
    # Tu saldo manda: transferable ya tiene en cuenta el tuyo.
    print(f"Podés transferir en su nombre: {balance.transferable}")
    print(f"Tu saldo: {totals.available}. El de tus clientes: {totals.customers_balance}")


def transfer(
    client: rayacash.RayaClient, customer_id: str, destination: str, amount: Decimal
) -> None:
    # Guardá la clave con la transferencia ANTES de llamar y reusala en cada reintento. Para volver
    # a intentar una que terminó failed, usá una clave nueva.
    key = str(uuid.uuid4())
    try:
        sent = client.psp.transfers.create(
            customer=customer_id, amount=amount, destination=destination, idempotency_key=key
        )
    except rayacash.UnprocessableEntityError as error:
        # INSUFFICIENT_BALANCE (tu saldo), CUSTOMER_INSUFFICIENT_BALANCE (el suyo), DESTINATION_*.
        print(f"No se pudo transferir: {error.message} ({error.code})")
        return
    except rayacash.ConflictError as error:
        # CUSTOMER_STATUS_CONFLICT: el cliente no está active o está bloqueado.
        print(f"Tu cliente no puede transferir ahora: {error.data}")
        return
    except (rayacash.APIConnectionError, rayacash.APIError) as error:
        # Sin respuesta o falla de nuestro lado: reintentá más tarde con la MISMA clave.
        print(f"Reintentá más tarde con la clave {error.idempotency_key}: {error.message}")
        return

    print(f"Transferencia {sent.id}: {sent.status}. Comisión, de tu saldo: {sent.fee}")
    if sent.status == "pending":
        print("Te avisamos con psp.transfer.sent o psp.transfer.failed.")


def block(client: rayacash.RayaClient, customer_id: str) -> None:
    customer = client.psp.customers.block(customer_id)
    # Sigue recibiendo transferencias, pero no puede enviar.
    print(f"{customer.id}: {customer.status} (bloqueado por {customer.blocked_by})")


def list_active(client: rayacash.RayaClient) -> None:
    for customer in client.psp.customers.list(status="active", limit=100).auto_paging_iter():
        print(customer.id, customer.external_reference, customer.balance)


def main() -> None:
    command, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    with rayacash.RayaClient() as client:
        try:
            if command == "crear":
                create(client, args[0])
            elif command == "saldo":
                show_balance(client, args[0])
            elif command == "transferir":
                transfer(client, args[0], args[1], Decimal(args[2]))
            elif command == "bloquear":
                block(client, args[0])
            elif command == "listar":
                list_active(client)
            else:
                print(__doc__)
        except rayacash.PermissionDeniedError as error:
            if error.code != "PSP_NOT_ACTIVATED":
                raise
            print("Activá Raya PSP desde Negocios › Raya PSP y esperá la aprobación.")


if __name__ == "__main__":
    main()
