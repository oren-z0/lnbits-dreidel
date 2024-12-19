import asyncio
from fastapi import APIRouter
from loguru import logger

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


from .views import *  # noqa: F401,F403,E402
from .views_api import *  # noqa: F401,F403,E402


scheduled_tasks: list[asyncio.Task] = []

def dreidel_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)

def dreidel_start():
    pass
