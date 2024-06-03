from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.hash import sha256_crypt

from ..db import get_db
from riche_questionnaire_back_end.models.users_models import User

user_router = APIRouter()


class UserCreate(BaseModel):
    name: str
    soName: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


@user_router.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = sha256_crypt.hash(user.password)
    db_user = User(
        name=user.name, soName=user.soName, email=user.email, password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "name": db_user.name, "soName": db_user.soName}


@user_router.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not sha256_crypt.verify(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"id": db_user.id, "name": db_user.name, "soName": db_user.soName}
