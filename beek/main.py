import io
from tkinter import Image
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from beek.routers.users import user_router
from beek.routers.forms import form_router
from constants import MEDIA_CONSTANTS
from sqlalchemy.orm import Session

import base64
import mimetypes
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.routing import APIWebSocketRoute

from urllib.parse import quote

from beek.decorators import chek_no_photo, run_in_parallel, header_api_key_auth
from constants import MEDIA_CONSTANTS
from .db import get_db
from fastapi import FastAPI


app = FastAPI(
    title="Bacend Riche App",
    description="Альтернативная документация [redocs](/redoc)",
    summary="Deadpool's favorite app. Nuff said.",
    version="0.0.1",
    timeout=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def docs():
    return RedirectResponse("/docs")


@app.get("/r")
def docs():
    return RedirectResponse("/redoc")


def apply_decorator_to_router(router, decorator):
    for route in router.routes:
        if hasattr(route, "endpoint"):
            if type(route) == APIWebSocketRoute:
                continue
            endpoint = route.endpoint
            if hasattr(endpoint, "__func__"):
                route.endpoint = decorator(getattr(endpoint, "__func__"))
            else:
                route.endpoint = decorator(endpoint)
    return router


app.include_router(
    apply_decorator_to_router(user_router, header_api_key_auth(_router="users")),
    prefix="/api/v1/users",
    tags=["users"],
)
app.include_router(
    apply_decorator_to_router(form_router, header_api_key_auth(_router="forms")),
    prefix="/api/v1/forms",
    tags=["forms"],
)


@app.api_route("/media/{razdel}/{rout}/{id}", methods=["GET", "HEAD"])
@run_in_parallel
@chek_no_photo
async def get_media_file(
    razdel: str, rout: str, id: int, scaling: int = None, db: Session = Depends(get_db)
):
    """Универсальная функция для получения медиа файлов

    Args:
        razdel (str): Раздел
        rout (str): псевдо название функции
        id (int): id записи
        scaling (int): уменьшить фото

    Returns:
        StreamingResponse: если файл есть его вернет / если нет вернет заглушку
    """

    model = MEDIA_CONSTANTS.get(razdel, {}).get(rout, None)

    if not model:
        return None

    media = db.query(model).get(id)

    if not media:
        return None

    if not media.media or not media.name:
        return None

    mime_type, _ = mimetypes.guess_type(media.name)

    encoded_data = media.media.split(",")[1]
    bytes_media = base64.b64decode(encoded_data)

    if scaling and mime_type.startswith("image"):
        image = Image.open(io.BytesIO(bytes_media))
        image = image.resize(
            (int(image.height / scaling), int(image.width / scaling)),
            Image.Resampling.LANCZOS,
        )
        img_byte_arr = io.BytesIO()
        image_format = mime_type.split("/")[-1].upper()
        image.save(img_byte_arr, format=image_format)
        bytes_media = img_byte_arr.getvalue()

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(media.name)}",
        "Content-Length": str(len(bytes_media)),
    }

    return StreamingResponse(iter([bytes_media]), media_type=mime_type, headers=headers)
