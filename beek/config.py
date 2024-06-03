from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, validator


class Settings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    REDIS: str

    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    base_url: str

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        dsn = f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}@{values['POSTGRES_SERVER']}/{values['POSTGRES_DB']}"
        print(f"[+] Data base url - {dsn}")
        return dsn

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
