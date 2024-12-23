from asyncio import Queue
from http import HTTPStatus
import json
import random
from time import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from fastapi import Depends, Query, Request
from fastapi.exceptions import HTTPException
from loguru import logger
from lnurl import encode as lnurl_encode

from lnbits.helpers import urlsafe_short_hash
from lnbits.core.services import pay_invoice

try:
    import Cryptodome.Random.random
    def dreidel_random():
        return Cryptodome.Random.random.randint(0, 3)
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

from .extension import dreidel_ext
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

@dreidel_ext.get("/api/v1/dreidels/{dreidel_id}/state")
async def api_dreidel_game_state(dreidel_id: str):
    dreidel = await get_dreidel(dreidel_id)
    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel game instance does not exist."
        )
    game_state = json.loads(dreidel.game_state)
    paid_amount = await _get_amount_paid(dreidel)
    if game_state["state"] == "initial":
        game_state["state"] = "funding"
        game_state["initial_funding_completed"] = False
        game_state["balances"] = [0] * dreidel.players
        game_state["current_player"] = 0
        game_state["funding_players"] = list(range(dreidel.players))
        game_state["after_funding_player"] = 0
        game_state["jackpot"] = 0
        game_state["payment_request_amount"], payment_hash, game_state["payment_request"] = await _create_dreidel_funding_invoice(
            dreidel, game_state["initial_funding_completed"]
        )
        game_state["updated_at"] = time()
        game_state["temporary_state"] = None
        await update_dreidel_game_state(dreidel, dreidel.wallet, game_state, payment_hash)
    elif paid_amount > 0:
        game_state["temporary_state"] = None
        game_state["paid_amount"] = paid_amount
        if game_state["state"] == "funding":
            game_state["jackpot"] += min(paid_amount, dreidel.bet_amount)
            game_state["balances"][game_state["current_player"]] += max(0, paid_amount - dreidel.bet_amount)
            game_state["funding_players"] = [player_index for player_index in game_state["funding_players"] if player_index != game_state["current_player"]]
            if len(game_state["funding_players"]) > 0:
                game_state["current_player"] = game_state["funding_players"][0]
            else:
                game_state["state"] = "playing"
                game_state["initial_funding_completed"] = True
                game_state["current_player"] = game_state["after_funding_player"]
        elif game_state["state"] == "playing":
            game_state["last_player"] = game_state["current_player"]
            game_state["dreidel_result"] = dreidel_random()
            if game_state["dreidel_result"] == 0: # Nisht
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 1: # Gantz
                game_state["balances"][game_state["current_player"]] += game_state["jackpot"]
                game_state["jackpot"] = 0
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 2: # Halb
                halve_amount = (game_state["jackpot"] + 1) // 2
                game_state["balances"][game_state["current_player"]] += halve_amount
                game_state["jackpot"] -= halve_amount
                game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            elif game_state["dreidel_result"] == 3: # Shtel
                if game_state["balances"][game_state["current_player"]] < dreidel.bet_amount:
                    game_state["state"] = "shtel"
                else:
                    game_state["balances"][game_state["current_player"]] -= dreidel.bet_amount
                    game_state["jackpot"] += dreidel.bet_amount
                    game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
            if game_state["jackpot"] <= 0:
                game_state["state"] = "funding"
                game_state["funding_players"] = [
                    (game_state["current_player"] + index) % dreidel.players
                    for index in range(dreidel.players)
                ]
                game_state["after_funding_player"] = game_state["current_player"]
                can_fund_players = [player_index for player_index in game_state["funding_players"] if game_state["balances"][player_index] >= dreidel.bet_amount]
                if len(can_fund_players) > 0:
                    game_state["temporary_state"] = json.loads(json.dumps(game_state))
                    for player_index in can_fund_players:
                        game_state["balances"][player_index] -= dreidel.bet_amount
                        game_state["jackpot"] += dreidel.bet_amount
                    game_state["funding_players"] = [player_index for player_index in game_state["funding_players"] if player_index not in can_fund_players]
                    if len(game_state["funding_players"]) > 0:
                        game_state["current_player"] = game_state["funding_players"][0]
                    else:
                        game_state["state"] = "playing"
                        # current_player is already set to after_funding_player
        elif game_state["state"] == "shtel":
            game_state["jackpot"] += paid_amount
            game_state["state"] = "playing"
            game_state["current_player"] = (game_state["current_player"] + 1) % dreidel.players
        game_state["payment_request_amount"], payment_hash, payment_request = await (
            _create_dreidel_spinning_invoice(dreidel)
            if game_state["state"] == "playing"
            else _create_dreidel_funding_invoice(dreidel, game_state["initial_funding_completed"])
        )
        game_state["payment_request"] = payment_request
        game_state["updated_at"] = time()
        await update_dreidel_game_state(dreidel, dreidel.wallet, game_state, payment_hash)
    game_state["spin_seconds"] = dreidel.spin_seconds
    game_state["ok"] = True
    return game_state

async def _create_dreidel_funding_invoice(dreidel: Dreidel, initial_funding_completed: bool):
    amount = dreidel.bet_amount + (0 if initial_funding_completed else dreidel.initial_balance)
    return (amount, *(await create_invoice(
        wallet_id=dreidel.wallet,
        amount=amount,
        memo=f"Funding dreidel game: {dreidel.memo}",
        extra={"tag": "dreidel", "id": dreidel.id},
    )))

async def _create_dreidel_spinning_invoice(dreidel: Dreidel):
    return (dreidel.spinning_price, *(await create_invoice(
        wallet_id=dreidel.wallet,
        amount=dreidel.spinning_price,
        memo=f"Spin dreidel: {dreidel.memo}",
        extra={"tag": "dreidel", "id": dreidel.id},
    )))

async def _get_amount_paid(dreidel: Dreidel) -> int: # in sats
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

        return payment.amount // 1000  # Convert msats to sats
    return 0

@dreidel_ext.post("/api/v1/dreidels/{dreidel_id}/end")
async def api_dreidel_end(req: Request, dreidel_id: str):
    dreidel = await get_dreidel(dreidel_id)
    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel game instance does not exist."
        )
    game_state = json.loads(dreidel.game_state)
    if game_state["state"] == "ended":
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Dreidel game already ended."
        )
    game_state["state"] = "ended"
    leftover_base = game_state["jackpot"] // dreidel.players
    leftover_remainder = game_state["jackpot"] % dreidel.players
    game_state["balances"] = [
        balance + leftover_base + (1 if player_index < leftover_remainder else 0)
        for player_index, balance in enumerate(game_state["balances"])
    ]
    game_state["jackpot"] = 0
    game_state["locked"] = False
    game_state["withdraw_links"] = [
        _build_withdraw_link(req, dreidel.id, player_index, balance * (100 - dreidel.service_fee_percent) // 100)
        for player_index, balance in enumerate(game_state["balances"])
    ]
    game_state["updated_at"] = time()
    await update_dreidel_game_state(dreidel, dreidel.wallet, game_state, "")
    return {"ok": True}

def _build_withdraw_link(req: Request, dreidel_id: str, player_index: int, balance: int) -> dict:
    k1 = urlsafe_b64encode(json.dumps([dreidel_id, player_index, urlsafe_short_hash()]).encode()).replace(b'=', b'.').decode()
    if balance <= 0:
        return {
            "status": "too_small"
        }
    api_dreidels_withdraw_url = req.url_for("api_dreidels_withdraw")
    scheme = "http" if api_dreidels_withdraw_url.hostname.endswith(".onion") else "https"
    api_dreidels_withdraw_url = api_dreidels_withdraw_url.replace(scheme=scheme)
    lnurl = f"{api_dreidels_withdraw_url}?k1={k1}"
    try:
        encoded_lnurl = lnurl_encode(lnurl)
    except:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to encode lnurl: {lnurl}"
        )
    return {
        "amount_sats": balance,
        "k1": k1,
        "status": "pending",
        "lnurl": encoded_lnurl,
    }


@dreidel_ext.get("/api/v1/dreidels-withdraw")
async def api_dreidels_withdraw(req: Request, k1: str, pr: str | None = None):
    try:
        data = json.loads(urlsafe_b64decode(k1.replace('.', '=')))
        if not isinstance(data, list) or len(data) != 3 or not isinstance(data[0], str) or not isinstance(data[1], int) or not isinstance(data[2], str):
            return {"status": "ERROR", "reason": "Invalid k1."}
        dreidel_id = data[0]
        player_index = data[1]
        dreidel = await get_dreidel(dreidel_id)
        if not dreidel:
            return {"status": "ERROR", "reason": "Invalid k1."}
        game_state = json.loads(dreidel.game_state)
        if game_state["state"] != "ended":
            return {"status": "ERROR", "reason": "Invalid k1."}
        if player_index < 0 or player_index >= len(game_state["withdraw_links"]):
            return {"status": "ERROR", "reason": "Invalid k1."}
        withdraw_link = game_state["withdraw_links"][player_index]
        if withdraw_link["status"] == "too_small":
            return {"status": "ERROR", "reason": "Invalid k1."}
        if withdraw_link["k1"] != k1:
            return {"status": "ERROR", "reason": "Invalid k1."}
        if withdraw_link["status"] != "pending":
            return {"status": "ERROR", "reason": "Already withdrawn."}
        amount_sats = withdraw_link["amount_sats"]
        if not pr:
            api_dreidels_withdraw_url = req.url_for("api_dreidels_withdraw")
            scheme = "http" if api_dreidels_withdraw_url.hostname.endswith(".onion") else "https"
            api_dreidels_withdraw_url = api_dreidels_withdraw_url.replace(scheme=scheme)
            return {
                "tag": "withdrawRequest",
                "callback": str(api_dreidels_withdraw_url), # same endpoint
                "k1": k1,
                "maxWithdrawable": amount_sats * 1000,
                "minWithdrawable": amount_sats * 1000,
                "defaultDescription": f"Dreidel game prize {dreidel_id} player {player_index + 1}",
            }
        if game_state["locked"]:
            return {"status": "ERROR", "reason": "Withdraw already being processed."}
        game_state["locked"] = True
        try:
            game_state["updated_at"] = time()
            await update_dreidel_game_state(dreidel, dreidel.wallet, game_state, "")
            dreidel = await get_dreidel(dreidel_id)
            if not dreidel:
                return {"status": "ERROR", "reason": "Dreidel game instance does not exist anymore."}
            game_state = json.loads(dreidel.game_state)
        except:
            return {"status": "ERROR", "reason": "Withdraw already being processed."}
        try:
            await pay_invoice(
                wallet_id=dreidel.wallet,
                payment_request=pr,
                max_sat=amount_sats,
                extra={"tag": "dreidel-withdraw", "id": dreidel_id, "player_index": player_index},
            )
            game_state["withdraw_links"][player_index]["status"] = "paid"
        except:
            return {"status": "ERROR", "reason": "Failed to pay invoice."}
        finally:
            game_state["locked"] = False
            game_state["updated_at"] = time()
            try:
                await update_dreidel_game_state(dreidel, dreidel.wallet, game_state, "")
            except:
                return {"status": "ERROR", "reason": "Critical error in unlocking withdraw-links state."}
        return {"status": "OK"}
    except:
        return {"status": "ERROR", "reason": "Internal error."}
