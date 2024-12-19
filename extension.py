from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_dreidel")

dreidel_ext: APIRouter = APIRouter(prefix="/dreidel", tags=["Dreidel"])

dreidel_static_files = [
    {
        "path": "/dreidel/static",
        "name": "dreidel_static",
    }
]

def dreidel_renderer():
    return template_renderer(["dreidel/templates"])
