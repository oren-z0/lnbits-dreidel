import json
from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from .extension import db
from .models import CreateDreidel, Dreidel, UpdateDreidel, UpdateDreidelGameState


async def create_dreidel(wallet_id: str, data: CreateDreidel) -> Dreidel:
    dreidel_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO dreidel.dreidels
        (id, wallet, memo, bet_amount, rotate_seconds, players, game_state)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dreidel_id,
            wallet_id,
            data.memo,
            data.bet_amount,
            data.rotate_seconds,
            data.players,
            json.dumps({
                "state": "initial",
            }),
        ),
    )

    dreidel = await get_dreidel(dreidel_id)
    assert dreidel, "Newly created dreidel couldn't be retrieved"
    return dreidel


async def update_dreidel(id: str, wallet_id: str, data: UpdateDreidel) -> Dreidel:
    await db.execute(
        """
        UPDATE dreidel.dreidels
        SET (memo, bet_amount, rotate_seconds) =
        (?, ?, ?)
        WHERE id = ? AND wallet = ?
        """,
        (
            data.memo,
            data.bet_amount,
            data.rotate_seconds,
            id,
            wallet_id,
        ),
    )

    dreidel = await get_dreidel(id)
    assert dreidel, "Updated dreidel couldn't be retrieved"
    return dreidel


async def update_dreidel_game_state(id: str, wallet_id: str, game_state: dict, payment_hash: str) -> Dreidel:
    await db.execute(
        """
        UPDATE dreidel.dreidels
        SET (game_state, payment_hash) =
        (?, ?)
        WHERE id = ? AND wallet = ?
        """,
        (json.dumps(game_state), payment_hash, id, wallet_id),
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
