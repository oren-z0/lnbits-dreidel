import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateDreidel(BaseModel):
    url: str = Query(...)
    memo: str = Query(...)
    description: str = Query(None)
    amount: int = Query(..., ge=0)
    remembers: bool = Query(...)


class CreateDreidelInvoice(BaseModel):
    amount: int = Query(..., ge=1)


class CheckDreidelInvoice(BaseModel):
    payment_hash: str = Query(...)


class Dreidel(BaseModel):
    id: str
    wallet: str
    url: str
    memo: str
    description: Optional[str]
    amount: int
    time: int
    remembers: bool

    @classmethod
    def from_row(cls, row: Row) -> "Dreidel":
        data = dict(row)
        data["remembers"] = bool(data["remembers"])
        return cls(**data)
