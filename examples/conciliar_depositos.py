"""Conciliar depósitos: suma las transferencias recibidas en un día, en sync y en async.

Solo lee (GET /v1/transfers): no crea ni mueve nada.

    RAYA_SECRET_KEY=raya_sk_live_… python examples/conciliar_depositos.py 2026-10-23
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import rayacash

ARGENTINA = timezone(timedelta(hours=-3))


def day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(), tzinfo=ARGENTINA)
    return start, start + timedelta(days=1)  # semiabierto: [inicio, fin)


def deposits_of(client: rayacash.RayaClient, day: date) -> Decimal:
    start, end = day_range(day)
    page = client.transfers.list(direction="inbound", created_gte=start, created_lt=end, limit=100)
    total = Decimal(0)
    for transfer in page.auto_paging_iter():
        # net_amount es lo que se sumó a tu saldo. Decimal(str(…)) para sumar exacto.
        total += Decimal(str(transfer.net_amount))
        print(transfer.id, transfer.counterparty.name, transfer.net_amount)
    return total


async def deposits_of_async(client: rayacash.RayaClient, day: date) -> Decimal:
    start, end = day_range(day)
    page = await client.transfers.list_async(
        direction="inbound", created_gte=start, created_lt=end, limit=100
    )
    total = Decimal(0)
    async for transfer in page.auto_paging_iter():
        total += Decimal(str(transfer.net_amount))
    return total


def main() -> None:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    with rayacash.RayaClient() as client:
        print(f"Total del {day}: ${deposits_of(client, day)}")

    async def run_async() -> None:
        async with rayacash.RayaClient() as client:
            print(f"Total del {day} (async): ${await deposits_of_async(client, day)}")

    asyncio.run(run_async())


if __name__ == "__main__":
    main()
