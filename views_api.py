from asyncio import Queue
from http import HTTPStatus
import json
from typing import Optional
from urllib import request

from fastapi import Depends, Query, Request, Response
from fastapi.exceptions import HTTPException
from loguru import logger

from lnbits.core.crud import get_standalone_payment, get_user
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    require_admin_key,
)

from . import dreidel_ext, paid_invoices
from .crud import (
    create_dreidel,
    delete_dreidel,
    get_dreidel,
    get_dreidels,
    update_dreidel,
)
from .models import CheckDreidelInvoice, CreateDreidel, CreateDreidelInvoice, Dreidel


@dreidel_ext.get("/api/v1/dreidels")
async def api_dreidels(
    wallet: WalletTypeInfo = Depends(get_key_type), all_wallets: bool = Query(False)
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [dreidel.dict() for dreidel in await get_dreidels(wallet_ids)]


@dreidel_ext.post("/api/v1/dreidels")
async def api_dreidel_create(
    data: CreateDreidel, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    dreidel = await create_dreidel(wallet_id=wallet.wallet.id, data=data)
    return dreidel.dict()


@dreidel_ext.patch("/api/v1/dreidels/{id}")
@dreidel_ext.put("/api/v1/dreidels/{id}")
async def api_dreidel_update(
    id: str, data: CreateDreidel, wallet: WalletTypeInfo = Depends(require_admin_key)
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


@dreidel_ext.post("/api/v1/dreidels/invoice/{dreidel_id}")
async def api_dreidel_create_invoice(data: CreateDreidelInvoice, dreidel_id: str):
    try:
        dreidel = await get_dreidel(dreidel_id)
        assert dreidel, "Dreidel not found"
        return await _create_dreidel_invoice(dreidel)
    except AssertionError as e:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))


@dreidel_ext.post("/api/v1/dreidels/check_invoice/{dreidel_id}")
async def api_paywal_check_invoice(
    request: Request, data: CheckDreidelInvoice, dreidel_id: str
):
    dreidel = await get_dreidel(dreidel_id)
    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel does not exist."
        )
    paid_amount = await _is_payment_made(dreidel, data.payment_hash)

    if paid_amount:
        return {"paid": True}

    return {"paid": False}

async def _create_dreidel_invoice(dreidel: Dreidel):
    payment_hash, payment_request = await create_invoice(
        wallet_id=dreidel.wallet,
        amount=dreidel.bet_amount,
        memo=f"{dreidel.memo}",
        extra={"tag": "dreidel", "id": dreidel.id},
    )
    return {"payment_hash": payment_hash, "payment_request": payment_request}


async def _is_payment_made(dreidel: Dreidel, payment_hash: str) -> int:
    try:
        status = await check_transaction_status(dreidel.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return 0

    if is_paid:
        payment = await get_standalone_payment(
            checking_id_or_hash=payment_hash, incoming=True, wallet_id=dreidel.wallet
        )
        assert payment, f"Payment not found for payment_hash: '{payment_hash}'."
        if payment.extra.get("tag", None) != "dreidel":
            return 0
        dreidel_id = payment.extra.get("id", None)
        if dreidel_id and dreidel_id != dreidel.id:
            return 0

        return payment.amount
    return 0
