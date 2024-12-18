import json
from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateDreidel, Dreidel


async def create_dreidel(wallet_id: str, data: CreateDreidel) -> Dreidel:
    dreidel_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO dreidel.dreidels
        (id, wallet, url, memo, amount)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            dreidel_id,
            wallet_id,
            data.url,
            data.memo,
            data.amount,
        ),
    )

    dreidel = await get_dreidel(dreidel_id)
    assert dreidel, "Newly created dreidel couldn't be retrieved"
    return dreidel


async def update_dreidel(id: str, wallet_id: str, data: CreateDreidel) -> Dreidel:
    await db.execute(
        """
        UPDATE dreidel.dreidels
        SET (wallet, url, memo, amount) =
        (?, ?, ?, ?)
        WHERE id = ? AND wallet = ?
        """,
        (
            wallet_id,
            data.url,
            data.memo,
            data.amount,
            id,
            wallet_id,
        ),
    )

    dreidel = await get_dreidel(id)
    assert dreidel, "Updated dreidel couldn't be retrieved"
    return dreidel


async def get_dreidel(dreidel_id: str) -> Optional[Dreidel]:
    row = await db.fetchone(
        "SELECT * FROM dreidel.dreidels WHERE id = ?", (dreidel_id,)
    )
    return Dreidel.from_row(row) if row else None


async def get_dreidels(wallet_ids: Union[str, List[str]]) -> List[Dreidel]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM dreidel.dreidels WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Dreidel.from_row(row) for row in rows]


async def delete_dreidel(dreidel_id: str) -> None:
    await db.execute("DELETE FROM dreidel.dreidels WHERE id = ?", (dreidel_id,))
