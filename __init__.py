import asyncio
from typing import List
from fastapi import APIRouter
from asyncio import Task
from loguru import logger

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import create_permanent_unique_task

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


from .tasks import wait_for_paid_invoices, paid_invoices  # noqa: F401,F403,E402
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
    task = create_permanent_unique_task("ext_dreidel", wait_for_paid_invoices)
    scheduled_tasks.append(task)
