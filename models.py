import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateDreidel(BaseModel):
    memo: str = Query(...)
    amount: int = Query(..., ge=0)


class CreateDreidelInvoice(BaseModel):
    amount: int = Query(..., ge=1)


class CheckDreidelInvoice(BaseModel):
    payment_hash: str = Query(...)


class Dreidel(BaseModel):
    id: str
    wallet: str
    memo: str
    amount: int
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Dreidel":
        data = dict(row)
        return cls(**data)
