import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateDreidel(BaseModel):
    memo: str = Query(...)
    bet_amount: int = Query(..., ge=1)
    rotate_seconds: int = Query(..., ge=1)
    players: int = Query(..., ge=1)

class UpdateDreidel(BaseModel):
    memo: str = Query(...)
    bet_amount: int = Query(..., ge=1)
    rotate_seconds: int = Query(..., ge=1)

class UpdateDreidelGameState(BaseModel):
    game_state: str = Query(...)
    payment_hash: str = Query(...)

class CreateDreidelInvoice(BaseModel):
    bet_amount: int = Query(..., ge=1)


class CheckDreidelInvoice(BaseModel):
    payment_hash: str = Query(...)


class Dreidel(BaseModel):
    id: str
    wallet: str
    memo: str
    bet_amount: int
    rotate_seconds: int
    players: int
    game_state: str
    payment_hash: str
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Dreidel":
        data = dict(row)
        return cls(**data)
