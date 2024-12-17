import json
from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class DreidelFileConfig(BaseModel):
    url: str
    headers: dict[str, str]
    # todo: nice to have:
    # expiration_time: Optional[int]
    # max_number_of_downloads: Optional[int]


class DreidelConfig(BaseModel):
    # possible types: 'url' and 'file'
    type: Optional[str] = "url"
    file_config: Optional[DreidelFileConfig] = None


class CreateDreidel(BaseModel):
    url: str = Query(...)
    memo: str = Query(...)
    description: str = Query(None)
    amount: int = Query(..., ge=0)
    remembers: bool = Query(...)
    extras: Optional[DreidelConfig] = None


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
    extras: Optional[DreidelConfig] = DreidelConfig()

    @classmethod
    def from_row(cls, row: Row) -> "Dreidel":
        data = dict(row)
        data["remembers"] = bool(data["remembers"])
        data["extras"] = (
            DreidelConfig(**json.loads(data["extras"])) if data["extras"] else None
        )
        return cls(**data)
