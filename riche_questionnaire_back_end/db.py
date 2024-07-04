from datetime import datetime
import mimetypes
from sqlalchemy.orm import RelationshipProperty, ColumnProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Date, DateTime, create_engine
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from .config import settings
from sqlalchemy import (
    Integer,
    Float,
    BigInteger,
    Boolean,
)
import redis
import os


engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=5000,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def identify_file_type(file_bytes):
    signatures = {
        b"%PDF": "application/pdf",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"\xFF\xD8\xFF": "image/jpeg",
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
        b"\x49\x49\x2A\x00": "image/tiff",
        b"\x4D\x4D\x00\x2A": "image/tiff",
        b"\x25\x50\x44\x46": "application/pdf",
        b"\x00\x01\x00\x00": "font/ttf",
        b"BM": "image/bmp",
        b"\x50\x4B\x03\x04\x14\x00\x06\x00": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        b"\x50\x4B\x03\x04\x14\x00\x06\x00": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        b"\x50\x4B\x03\x04\x14\x00\x06\x00": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        b"\x50\x4B\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    for signature, mime_type in signatures.items():
        if file_bytes.startswith(signature):
            return mime_type

    return "unknown"


def getRedis():
    rconnect = redis.Redis(
        host=os.environ.get("REDIS"), port=6379, decode_responses=True
    )
    return rconnect


def getRedisClaster():
    rconnect = redis.RedisCluster(
        host=os.environ.get("REDIS"), port=6379, decode_responses=True
    )
    return rconnect


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


from sqlalchemy.orm import declarative_base, DeclarativeMeta


class CustomMeta(DeclarativeMeta):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if "custom_filed" in dct:
            custom_filed = dct["custom_filed"]
            for key, value in custom_filed.items():
                data = value.get("data", {})
                values = data.get("values", None)
                if values is not None and not callable(values):
                    raise ValueError(
                        f"Ошибка в классе {name}: 'values' должен быть экземпляром функции в 'custom_filed' для '{key}'"
                    )


class BaseMixin:

    noSelektFiled = ["id"]

    @staticmethod
    def get_class_by_foreign_key(model_class, column_name):
        column = getattr(model_class, column_name, None)
        if column is not None and hasattr(column, "foreign_keys"):
            fk = next(iter(column.foreign_keys), None)
            if fk:
                referenced_table = fk.column.table
                for cls in Base.registry.mappers:
                    if (
                        hasattr(cls.class_, "__table__")
                        and cls.class_.__table__ == referenced_table
                    ):
                        return cls.class_
        return None

    @classmethod
    def info(cls):
        return f"{cls.__name__}"

    @classmethod
    def get_items_to_selekt(cls):
        db: Session = SessionLocal()
        data = [
            {
                "label": item.__str__(),
                "value": item.id,
            }
            for item in db.query(cls)
        ]
        db.close()
        return data


Base = declarative_base(cls=BaseMixin, metaclass=CustomMeta)
