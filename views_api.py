from asyncio import Queue
from http import HTTPStatus
import json
from typing import Optional
from urllib import request
import random
from time import time
from fastapi import Depends, Query, Request, Response
from fastapi.exceptions import HTTPException
from loguru import logger

try:
    from Cryptodome import Random
    def dreidel_random():
        return Random.random.randint(0, 3)
except ImportError:
    def dreidel_random():
        return random.randint(0, 3)

from lnbits.core.crud import get_standalone_payment, get_user
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    require_admin_key,
)

from . import dreidel_ext
from .crud import (
    create_dreidel,
    delete_dreidel,
    get_dreidel,
    get_dreidels,
    update_dreidel,
    update_dreidel_game_state,
)
from .models import CreateDreidel, UpdateDreidel, Dreidel


@dreidel_ext.get("/api/v1/dreidels")
async def api_dreidels(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    results = []
    for dreidel in await get_dreidels(wallet_ids):
        dreidel_dict = dreidel.dict()
        del dreidel_dict["payment_hash"]
        results.append(dreidel_dict)

    return results


@dreidel_ext.post("/api/v1/dreidels")
async def api_dreidel_create(
    data: CreateDreidel, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    dreidel = await create_dreidel(wallet_id=wallet.wallet.id, data=data)
    return dreidel.dict()


@dreidel_ext.patch("/api/v1/dreidels/{id}")
@dreidel_ext.put("/api/v1/dreidels/{id}")
async def api_dreidel_update(
    id: str, data: UpdateDreidel, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    dreidel = await update_dreidel(id=id, wallet_id=wallet.wallet.id, data=data)
    return dreidel.dict()


@dreidel_ext.delete("/api/v1/dreidels/{dreidel_id}")
async def api_dreidel_delete(
    dreidel_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    dreidel = await get_dreidel(dreidel_id)

    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel does not exist."
        )

    if dreidel.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your dreidel."
        )

    await delete_dreidel(dreidel_id)
    return "", HTTPStatus.NO_CONTENT

@dreidel_ext.get("/api/v1/dreidels/{dreidel_id}/game_state")
async def api_dreidel_game_state(dreidel_id: str):
    dreidel = await get_dreidel(dreidel_id)
    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel game instance does not exist."
        )
    game_state = json.loads(dreidel.game_state)
    paid_amount_msats = await _get_amount_paid(dreidel)
    if game_state["state"] == "initial":
        game_state["state"] = "initial_funding"
        game_state["balances"] = [0] * dreidel.players
        game_state["current_player"] = 0
        game_state["jackpot"] = 0
        payment_hash, payment_request = await _create_dreidel_invoice(dreidel)
        game_state["payment_request"] = payment_request
        game_state["updated_at"] = time()
        await update_dreidel_game_state(dreidel_id, dreidel.wallet, game_state, payment_hash)
    elif paid_amount_msats > 0:
        game_state["jackpot"] += paid_amount_msats
        if game_state["state"] == "initial_funding":
            game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            if game_state["current_player"] == 0:
                game_state["state"] = "playing"
        elif game_state["state"] == "playing":
            game_state["dreidel_result"] = dreidel_random()
            if game_state["dreidel_result"] == 0: # Nisht
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 1: # Gantz
                game_state["balances"][game_state["current_player"]] += game_state["jackpot"]
                game_state["jackpot"] = 0
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 2: # Halb
                halve_amount = game_state["jackpot"] // 2
                game_state["balances"][game_state["current_player"]] += halve_amount
                game_state["jackpot"] -= halve_amount
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 3: # Shtel
                game_state["state"] = "shtel"
        elif game_state["state"] == "shtel":
            game_state["state"] = "playing"
            game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
        payment_hash, payment_request = await _create_dreidel_invoice(dreidel)
        game_state["payment_request"] = payment_request
        game_state["updated_at"] = time()
        await update_dreidel_game_state(dreidel_id, dreidel.wallet, game_state, payment_hash)
    game_state["rotate_seconds"] = dreidel.rotate_seconds
    game_state["ok"] = True
    return dreidel.game_state

async def _create_dreidel_invoice(dreidel: Dreidel):
    return await create_invoice(
        wallet_id=dreidel.wallet,
        amount=dreidel.bet_amount,
        memo=f"{dreidel.memo}",
        extra={"tag": "dreidel", "id": dreidel.id},
    )


async def _get_amount_paid(dreidel: Dreidel) -> int: # in millisats
    if not dreidel.payment_hash:
        return 0
    try:
        status = await check_transaction_status(dreidel.wallet, dreidel.payment_hash)
        is_paid = not status.pending
    except Exception:
        return 0
    if is_paid:
        payment = await get_standalone_payment(
            checking_id_or_hash=dreidel.payment_hash, incoming=True, wallet_id=dreidel.wallet
        )
        if not payment or payment.extra.get("tag", None) != "dreidel":
            return 0
        dreidel_id = payment.extra.get("id", None)
        if dreidel_id and dreidel_id != dreidel.id:
            return 0

        return payment.amount
    return 0
