from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from fastapi.security import OAuth2PasswordBearer
import jwt

load_dotenv()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expiration = datetime.utcnow() + expires_delta
    to_encode.update({"expiration": expiration.strftime("%Y-%m-%d")})
    encoded_jwt = jwt.encode(
        to_encode, os.environ.get("SECRET_KEY"), algorithm=os.environ.get("ALGORITHM")
    )
    return encoded_jwt


def decode_access_token(token):
    try:
        payload = jwt.decode(
            token,
            os.environ.get("SECRET_KEY"),
            algorithms=os.environ.get("ALGORITHM"),
        )
        user_id = payload["user_id"]
        user_email = payload["user_email"]
        user_password = payload["user_password"]
        expiration = datetime.strptime(payload["expiration"], "%Y-%m-%d")
        is_token_expired = expiration >= datetime.now()
        return user_id, user_email, user_password, is_token_expired
    except:
        return None, None, None, False


data_keys_Ayth = {
    "test_key": ["__all__"],
}
