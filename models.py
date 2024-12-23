import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateDreidel(BaseModel):
    memo: str = Query(..., max_length=100)
    bet_amount: int = Query(..., ge=1)
    spin_seconds: int = Query(..., ge=1, le=600)
    players: int = Query(..., ge=2, le=50)
    service_fee_percent: int = Query(..., ge=0, le=100)

class UpdateDreidel(BaseModel):
    memo: str = Query(...)
    bet_amount: int = Query(..., ge=1)
    spin_seconds: int = Query(..., ge=1)
    service_fee_percent: int = Query(..., ge=0, le=100)

class UpdateDreidelGameState(BaseModel):
    game_state: str = Query(...)
    payment_hash: str = Query(...)

class Dreidel(BaseModel):
    id: str
    wallet: str
    memo: str
    bet_amount: int
    spin_seconds: int
    players: int
    game_state: str
    payment_hash: str
    time: int
    service_fee_percent: int

    @classmethod
    def from_row(cls, row: Row) -> "Dreidel":
        data = dict(row)
        return cls(**data)
