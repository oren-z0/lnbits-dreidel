from http import HTTPStatus

from fastapi import Depends
from fastapi.exceptions import HTTPException
from fastapi.requests import Request

from lnbits.core.models import User
from lnbits.decorators import check_user_exists

from . import dreidel_ext, dreidel_renderer
from .crud import get_dreidel


@dreidel_ext.get("/")
async def index(request: Request, user: User = Depends(check_user_exists)):
    return dreidel_renderer().TemplateResponse(
        "dreidel/index.html", {"request": request, "user": user.dict()}
    )


@dreidel_ext.get("/{dreidel_id}")
async def display(request: Request, dreidel_id: str):
    dreidel = await get_dreidel(dreidel_id)
    if not dreidel:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Dreidel does not exist."
        )
    return dreidel_renderer().TemplateResponse(
        "dreidel/display.html", {"request": request, "dreidel": dreidel}
    )
