from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import random

from ..db import get_db
from beek.models.users_models import User, Form

form_router = APIRouter()


def gen_links(count=5):
    return "".join(str(random.randint(0, 10000000)) for _ in range(count))


@form_router.post("/add")
async def add_form(email: str, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    url = gen_links()
    db_form = Form(user_id_creat=db_user.id, url=url)
    db.add(db_form)
    db.commit()
    db.refresh(db_form)
    return {"url": db_form.url}
