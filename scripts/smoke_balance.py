"""Prueba manual contra la API real: solo consulta el saldo (GET /v1/balance).

No crea ni mueve nada. Nunca corre en CI: lo corrés vos, con tu clave en la variable de
entorno (nunca la pegues en un chat ni en el repositorio).

    RAYA_SECRET_KEY=raya_sk_live_… uv run python scripts/smoke_balance.py
"""

from __future__ import annotations

import rayacash


def main() -> None:
    rayacash.log = "info"
    with rayacash.RayaClient() as client:
        balance = client.balance.retrieve()
    request_id = balance.last_response.request_id if balance.last_response else None
    print(f"Saldo disponible: ${balance.available} {balance.currency} (request {request_id})")


if __name__ == "__main__":
    main()
