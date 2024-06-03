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


from sqlalchemy import event

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
    async def get_empty_template(
        cls,
        get_RelationshipProperty=True,
        default_value={},
        default_values={},
        custom_noSelektFiled=[],
    ):
        custom_filed = getattr(cls, "custom_filed", {})
        noSelektFiled = getattr(cls, "noSelektFiled", [])
        noSelektFiled = noSelektFiled + custom_noSelektFiled
        template = {}
        objects = vars(cls)
        mapper = inspect(cls)
        for name in objects:
            if not name in noSelektFiled:
                _name = None
                isForeignKey = False
                if name in mapper.attrs:
                    _name = mapper.attrs[name]
                    if isinstance(_name, ColumnProperty):
                        if _name.columns[0].foreign_keys:
                            isForeignKey = True
                if (
                    name in custom_filed
                    or isinstance(_name, (RelationshipProperty))
                    or isForeignKey
                ) and get_RelationshipProperty:
                    if name in cls.__mapper__.relationships:
                        articles_class_ref = cls.__mapper__.relationships[
                            name
                        ].entity.class_
                        articles_class = articles_class_ref()
                    else:

                        _class = Base.get_class_by_foreign_key(cls, name)
                        if _class:
                            articles_class = _class()
                        else:
                            articles_class = None
                    cusotm_data = custom_filed.get(name, {})
                    template[name] = {
                        "value": (
                            [
                                await articles_class.get_empty_template(
                                    get_RelationshipProperty=False,
                                    default_value=default_value,
                                    custom_noSelektFiled=custom_noSelektFiled,
                                )
                            ]
                            if (
                                (
                                    cusotm_data.get("defaultValue", False)
                                    or cusotm_data.get("type", "MULTI") == "MULTI"
                                )
                                and articles_class
                            )
                            else default_value[name] if name in default_value else []
                        ),
                        "doc": (
                            objects[name].property.doc
                            if objects[name].property.doc
                            else ""
                        ),
                        "data": {
                            "values": (
                                default_values.get(name, [])
                                if name in default_values
                                else (
                                    articles_class.get_items_to_selekt()
                                    if articles_class
                                    else []
                                )
                            ),
                            "isMulti": False,
                            "showPhoto": True,
                            "tags": False,
                            **cusotm_data.get("data", {}),
                        },
                        "type": cusotm_data.get("type", "SELEKT"),
                        "mainKey": cusotm_data.get("mainKey", "name"),
                        "color": cusotm_data.get("color", False),
                        "important": cusotm_data.get("important", False),
                        "active": cusotm_data.get("active", False),
                        "otherFiles": cusotm_data.get("otherFiles", False),
                    }

                    if callable(template[name].get("data").get("values")):
                        template[name]["data"]["values"] = template[name]["data"][
                            "values"
                        ]()

                    if cusotm_data.get("type", "SELEKT") == "HTML":
                        template[name]["value"] = ""

                elif hasattr(objects[name], "doc"):
                    if name in custom_filed:
                        if name in cls.__mapper__.relationships:
                            articles_class_ref = cls.__mapper__.relationships[
                                name
                            ].entity.class_
                            articles_class = articles_class_ref()
                        else:

                            _class = Base.get_class_by_foreign_key(cls, name)
                            if _class:
                                articles_class = _class()
                            else:
                                articles_class = None
                        cusotm_data = custom_filed.get(name, {})

                        template[name] = {
                            "value": (
                                default_value[name] if name in default_value else []
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "data": {
                                "values": (
                                    default_values.get(name, [])
                                    if name in default_values
                                    else (
                                        articles_class.get_items_to_selekt()
                                        if articles_class
                                        else []
                                    )
                                ),
                                "isMulti": False,
                                "showPhoto": True,
                                "tags": False,
                                **cusotm_data.get("data", {}),
                            },
                            "type": cusotm_data.get("type", "SELEKT"),
                            "mainKey": cusotm_data.get("mainKey", "name"),
                            "color": cusotm_data.get("color", False),
                            "important": cusotm_data.get("important", False),
                            "active": cusotm_data.get("active", False),
                            "otherFiles": cusotm_data.get("otherFiles", False),
                        }
                        if callable(template[name].get("data").get("values")):
                            template[name]["data"]["values"] = template[name]["data"][
                                "values"
                            ]()

                        if cusotm_data.get("type", "SELEKT") == "HTML":
                            template[name]["value"] = ""

                    elif isinstance(objects[name].property.columns[0].type, Float):
                        template[name] = {
                            "value": (
                                default_value[name]
                                if name in default_value
                                else (
                                    objects[name].default.arg
                                    if objects[name].default
                                    else 0.0
                                )
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "type": str(objects[name].property.columns[0].type),
                        }
                    elif isinstance(objects[name].property.columns[0].type, Boolean):
                        template[name] = {
                            "value": (
                                default_value[name]
                                if name in default_value
                                else (
                                    objects[name].default.arg
                                    if objects[name].default
                                    else False
                                )
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "type": "SELEKT",
                            "data": {
                                "isMulti": False,
                                "values": [
                                    {
                                        "label": "Нет",
                                        "value": False,
                                    },
                                    {
                                        "label": "Да",
                                        "value": True,
                                    },
                                ],
                                "showPgoto": False,
                            },
                        }
                    elif isinstance(
                        objects[name].property.columns[0].type, BigInteger
                    ) or isinstance(objects[name].property.columns[0].type, Integer):
                        template[name] = {
                            "value": (
                                default_value[name]
                                if name in default_value
                                else (
                                    objects[name].default.arg
                                    if objects[name].default
                                    else 0
                                )
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "type": str(objects[name].property.columns[0].type),
                        }
                    elif isinstance(
                        objects[name].property.columns[0].type, DateTime
                    ) or isinstance(objects[name].property.columns[0].type, Date):
                        template[name] = {
                            "value": None,
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "type": str(objects[name].property.columns[0].type),
                        }
                    else:
                        template[name] = {
                            "value": (
                                default_value[name]
                                if name in default_value
                                else (
                                    objects[name].default.arg
                                    if objects[name].default
                                    else ""
                                )
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "type": str(objects[name].property.columns[0].type),
                        }
                else:

                    if name in custom_filed:
                        if name in cls.__mapper__.relationships:
                            articles_class_ref = cls.__mapper__.relationships[
                                name
                            ].entity.class_
                            articles_class = articles_class_ref()
                        else:

                            _class = Base.get_class_by_foreign_key(cls, name)
                            if _class:
                                articles_class = _class()
                            else:
                                articles_class = None
                        cusotm_data = custom_filed.get(name, {})
                        template[name] = {
                            "value": (
                                default_value[name] if name in default_value else []
                            ),
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "data": {
                                "values": (
                                    default_values.get(name, [])
                                    if name in default_values
                                    else (
                                        articles_class.get_items_to_selekt()
                                        if articles_class
                                        else []
                                    )
                                ),
                                "isMulti": False,
                                "showPhoto": True,
                                "tags": False,
                                **cusotm_data.get("data", {}),
                            },
                            "type": cusotm_data.get("type", "SELEKT"),
                            "mainKey": cusotm_data.get("mainKey", "name"),
                            "color": cusotm_data.get("color", False),
                            "important": cusotm_data.get("important", False),
                            "active": cusotm_data.get("active", False),
                            "otherFiles": cusotm_data.get("otherFiles", False),
                        }
        return template

    @classmethod
    async def get_data_prod(
        cls,
        _object=None,
        get_RelationshipProperty=True,
        custom_noSelektFiled=[],
        default_values={},
    ):
        from constants import MEDIA_CLASS_CONSTANTS

        custom_filed = getattr(cls, "custom_filed", {})
        noSelektFiled = getattr(cls, "noSelektFiled", [])
        noSelektFiled = noSelektFiled + custom_noSelektFiled
        template = {}
        objects = vars(cls)
        db = SessionLocal()
        mapper = inspect(cls)
        for name in objects:
            if not name in noSelektFiled:
                _name = None
                isForeignKey = False
                if name in mapper.attrs:
                    _name = mapper.attrs[name]
                    if isinstance(_name, ColumnProperty):
                        if _name.columns[0].foreign_keys:
                            isForeignKey = True
                if (
                    name in custom_filed
                    or isinstance(_name, (RelationshipProperty))
                    or isForeignKey
                ) and get_RelationshipProperty:

                    if name in cls.__mapper__.relationships:
                        articles_class_ref = cls.__mapper__.relationships[
                            name
                        ].entity.class_
                        articles_class = articles_class_ref()
                    else:
                        _class = Base.get_class_by_foreign_key(cls, name)
                        if _class:
                            articles_class = _class()
                        else:
                            articles_class = None
                    cusotm_data = custom_filed.get(name, {})

                    data = []
                    if cusotm_data.get("type", "SELEKT") == "SELEKT":

                        data = getattr(_object, _name.key, [])
                        if isinstance(data, list):
                            data = [item.id for item in data]
                        else:
                            data = [data]

                    elif cusotm_data.get("type", "SELEKT") == "MULTI":

                        if isinstance(getattr(_object, _name.key, []), list):
                            for sub_object in getattr(_object, _name.key, []):
                                if isinstance(_name, (RelationshipProperty)):
                                    data.append(
                                        await articles_class.get_data_prod(
                                            sub_object, False, custom_noSelektFiled
                                        )
                                    )
                        else:
                            data.append(getattr(_object, _name.key, []))
                        if len(data) == 0:
                            data = [
                                await articles_class.get_empty_template(
                                    False, custom_noSelektFiled=custom_noSelektFiled
                                )
                            ]

                    elif cusotm_data.get("type", "SELEKT") == "MEDIA":
                        files = []
                        for media in getattr(_object, _name.key, []):
                            id_media = getattr(media, "id")
                            name_media = getattr(media, "name", None)

                            if name_media is None:
                                continue

                            if type(media).__name__ in MEDIA_CLASS_CONSTANTS:
                                path = MEDIA_CLASS_CONSTANTS.get(type(media).__name__)

                            mime_type, _ = mimetypes.guess_type(name_media)

                            files.append(
                                {
                                    "file": "File",
                                    "preview": f"/media/{path}/{id_media}",
                                    "name": name_media,
                                    "type": (
                                        "image"
                                        if mime_type.startswith("image")
                                        else (
                                            "video"
                                            if mime_type.startswith("video")
                                            else "over"
                                        )
                                    ),
                                    "id": id_media,
                                }
                            )
                        data = files
                    elif cusotm_data.get("type", "SELEKT") == "HTML":
                        data = getattr(_object, _name.key, "")
                    else:
                        data = [
                            articles_class.get_value_class_noRp(i)
                            for i in getattr(_object, _name.key, [])
                        ]

                    template[name] = {
                        "value": (data),
                        "doc": (
                            objects[name].property.doc
                            if objects[name].property.doc
                            else ""
                        ),
                        "data": {
                            "values": (
                                default_values.get(name, [])
                                if name in default_values
                                else (
                                    articles_class.get_items_to_selekt()
                                    if articles_class
                                    else []
                                )
                            ),
                            "isMulti": False,
                            "showPhoto": True,
                            "tags": False,
                            **cusotm_data.get("data", {}),
                        },
                        "type": cusotm_data.get("type", "SELEKT"),
                        "mainKey": cusotm_data.get("mainKey", "name"),
                        "color": cusotm_data.get("color", False),
                        "important": cusotm_data.get("important", False),
                        "active": cusotm_data.get("active", False),
                        "otherFiles": cusotm_data.get("otherFiles", False),
                    }
                    if callable(template[name].get("data").get("values")):
                        template[name]["data"]["values"] = template[name]["data"][
                            "values"
                        ]()
                elif isinstance(objects[name], InstrumentedAttribute):
                    if name in custom_filed:
                        data = []
                        if name in cls.__mapper__.relationships:
                            articles_class_ref = cls.__mapper__.relationships[
                                name
                            ].entity.class_
                            articles_class = articles_class_ref()
                        else:
                            _class = Base.get_class_by_foreign_key(cls, name)
                            if _class:
                                articles_class = _class()
                            else:
                                articles_class = None
                        cusotm_data = custom_filed.get(name, {})

                        if cusotm_data.get("type", "SELEKT") == "MEDIA":
                            # files = []
                            # if isinstance(getattr(_object, _name.key, []), dict):
                            #     for media in getattr(_object, _name.key, []):
                            #         data_media = getattr(
                            #             media, cusotm_data.get("mediaKey", "media")
                            #         )
                            #         files.append(
                            #             {
                            #                 "file": "File",
                            #                 "preview": data_media,
                            #                 "data": data_media,
                            #             }
                            #         )

                            # else:
                            #     media = getattr(_object, _name.key, False)
                            #     if media:
                            #         files.append(
                            #             {
                            #                 "file": "File",
                            #                 "preview": f"{media}",
                            #                 "data": f"{media}",
                            #                 "name": "test",
                            #             }
                            #         )
                            # data = files
                            data = []
                        elif cusotm_data.get("type", "SELEKT") == "SELEKT":
                            data = getattr(_object, _name.key, [])
                            if isinstance(data, list):
                                data = [item.id for item in data]
                            else:
                                data = [data]

                        template[name] = {
                            "value": data,
                            "doc": (
                                objects[name].property.doc
                                if objects[name].property.doc
                                else ""
                            ),
                            "data": {
                                "values": (
                                    default_values.get(name, [])
                                    if name in default_values
                                    else (
                                        articles_class.get_items_to_selekt()
                                        if articles_class
                                        else []
                                    )
                                ),
                                "isMulti": False,
                                "showPhoto": True,
                                "tags": False,
                                **cusotm_data.get("data", {}),
                            },
                            "type": cusotm_data.get("type", "SELEKT"),
                            "mainKey": cusotm_data.get("mainKey", "name"),
                            "color": cusotm_data.get("color", False),
                            "important": cusotm_data.get("important", False),
                            "active": cusotm_data.get("active", False),
                            "otherFiles": cusotm_data.get("otherFiles", False),
                        }
                    elif hasattr(objects[name], "doc"):
                        if isinstance(objects[name].property.columns[0].type, Float):
                            template[name] = {
                                "value": getattr(_object, _name.key, ""),
                                "doc": (
                                    objects[name].property.doc
                                    if objects[name].property.doc
                                    else ""
                                ),
                                "type": str(objects[name].property.columns[0].type),
                            }
                        elif isinstance(objects[name].property.columns[0].type, Date):
                            date = getattr(_object, _name.key, None)
                            if date:
                                date = date.strftime("%d.%m.%y")
                            template[name] = {
                                "value": date,
                                "doc": (
                                    objects[name].property.doc
                                    if objects[name].property.doc
                                    else ""
                                ),
                                "type": str(objects[name].property.columns[0].type),
                            }
                        elif isinstance(
                            objects[name].property.columns[0].type, Boolean
                        ):
                            template[name] = {
                                "value": (getattr(_object, _name.key, False)),
                                "doc": (
                                    objects[name].property.doc
                                    if objects[name].property.doc
                                    else ""
                                ),
                                "type": "SELEKT",
                                "data": {
                                    "isMulti": False,
                                    "values": [
                                        {
                                            "label": "Нет",
                                            "value": False,
                                        },
                                        {
                                            "label": "Да",
                                            "value": True,
                                        },
                                    ],
                                    "showPgoto": False,
                                },
                            }
                        else:
                            template[name] = {
                                "value": getattr(_object, _name.key, ""),
                                "doc": (
                                    objects[name].property.doc
                                    if objects[name].property.doc
                                    else ""
                                ),
                                "type": str(objects[name].property.columns[0].type),
                            }
        db.close()

        return template

    @classmethod
    def create_for_template(
        _cls,
        formData,
        db: Session = SessionLocal(),
        custom_value={},
    ):
        cls = _cls()
        model_relationship = []
        for item in formData:

            _type = formData[item].get("type")
            _data = formData[item]
            if (
                "VARCHAR" in _type
                or "TEXT" in _type
                or "FLOAT" in _type
                or "INTEGER" in _type
                or "HTML" in _type
                or "BIGINT" in _type
            ):
                setattr(cls, item, _data.get("value", None))
            else:
                match _type:
                    case "SELEKT":
                        _isMulti = _data.get("isMulti", False)
                        if (
                            isinstance(_data.get("value", []), bool)
                            or len(_data.get("value", [])) != 0
                        ):
                            if _isMulti:
                                model_relationship = []
                                for _item in _data.get("value", []):
                                    articles_class_ref = cls.__mapper__.relationships[
                                        item
                                    ].entity.class_
                                    articles_class = articles_class_ref()
                                    for _model_key in _item:
                                        _model_value = _item[_model_key].get(
                                            "value", None
                                        )
                                        setattr(
                                            articles_class, _model_key, _model_value
                                        )
                                    model_relationship.append(articles_class)
                                    setattr(cls, item, model_relationship)
                            else:
                                mapper = inspect(cls.__class__)
                                property = mapper.attrs[item]
                                if isinstance(property, RelationshipProperty):
                                    related_instances = []
                                    for id in _data.get("value", []):
                                        if isinstance(id, int):
                                            related_instances.append(
                                                db.query(property.mapper.class_).get(id)
                                            )
                                    setattr(cls, item, related_instances)
                                elif isinstance(property, ColumnProperty):
                                    value = None
                                    if isinstance(_data.get("value", []), bool):
                                        value = _data.get("value")
                                    elif not isinstance(
                                        _data.get("value")[0], (list, dict)
                                    ):
                                        value = _data.get("value")[0]
                                    setattr(cls, item, value)
                    case "MULTI":
                        model_relationship = []
                        for _item in _data.get("value", []):
                            articles_class_ref = cls.__mapper__.relationships[
                                item
                            ].entity.class_
                            articles_class = articles_class_ref()
                            for _model_key in _item:
                                if (_item[_model_key].get("type", None)) == "MEDIA":
                                    _arrauItems = _item[_model_key].get("value", [])
                                    _model_value = None
                                    if len(_arrauItems) > 0:
                                        _arrauItem = _arrauItems[0].get("data", "")
                                        _model_value = _arrauItem
                                    if (
                                        not _model_value is None
                                        and not isinstance(_model_value, bool)
                                        and len(_model_value) == 0
                                    ):
                                        _model_value = None
                                elif (_item[_model_key].get("type", None)) == "SELEKT":
                                    _model_value = (
                                        False
                                        if isinstance(
                                            _item[_model_key].get("value", []), bool
                                        )
                                        else []
                                    )
                                    _isMulti = (
                                        _item[_model_key]
                                        .get("data", {})
                                        .get("isMulti", False)
                                    )
                                    if (
                                        isinstance(
                                            _item[_model_key].get("value", []), bool
                                        )
                                        or len(_item[_model_key].get("value", [])) != 0
                                    ):

                                        _model_relationship = []
                                        sub_model_relationship = []

                                        _articles_class = None

                                        articles_class_ref = (
                                            cls.__mapper__.relationships[
                                                item
                                            ].entity.class_
                                        )
                                        if articles_class_ref:
                                            _articles_class = articles_class_ref()
                                            if (
                                                (_model_key)
                                                in _articles_class.__mapper__.relationships
                                            ):
                                                sub_articles_class = _articles_class.__mapper__.relationships[
                                                    _model_key
                                                ].entity.class_

                                        if _isMulti:
                                            for _item_value in _item[_model_key].get(
                                                "value", []
                                            ):
                                                if sub_articles_class:
                                                    item_value = db.query(
                                                        sub_articles_class
                                                    ).get(_item_value)
                                                    sub_model_relationship.append(
                                                        item_value
                                                    )
                                                elif articles_class:
                                                    item_value = db.query(
                                                        articles_class
                                                    ).get(_item_value)
                                                    _model_relationship.append(
                                                        item_value
                                                    )
                                            if len(sub_model_relationship) != 0:
                                                _model_value = sub_model_relationship
                                            else:
                                                _model_value = _model_relationship
                                        else:
                                            if (
                                                isinstance(
                                                    _item[_model_key].get("value", []),
                                                    list,
                                                )
                                                and len(
                                                    _item[_model_key].get("value", [])
                                                )
                                                > 0
                                            ):
                                                if sub_articles_class:
                                                    _model_value = [
                                                        db.query(
                                                            sub_articles_class
                                                        ).get(
                                                            _item[_model_key].get(
                                                                "value", []
                                                            )[0]
                                                        )
                                                    ]
                                                else:
                                                    _model_value = _item[
                                                        _item[_model_key].get(
                                                            "value", []
                                                        )[0]
                                                    ]
                                            else:
                                                _model_value = _item[_model_key].get(
                                                    "value", False
                                                )
                                else:
                                    _model_value = _item[_model_key].get("value", None)
                                setattr(articles_class, _model_key, _model_value)
                            model_relationship.append(articles_class)
                        setattr(cls, item, model_relationship)

                    case "MEDIA":
                        model_relationship = []
                        articles_class_ref = cls.__mapper__.relationships[
                            item
                        ].entity.class_
                        for _item in _data.get("value", []):
                            articles_class = articles_class_ref()
                            setattr(articles_class, "name", _item.get("name", None))
                            setattr(
                                articles_class,
                                "media",
                                _item.get("data", None),
                            )
                            model_relationship.append(articles_class)
                        setattr(cls, item, model_relationship)
                    case "DATETIME":
                        date = _data.get("value", None)
                        if date:
                            date = datetime.strptime(date, "%d.%m.%y %H:%M:%S")
                        setattr(cls, item, date)
                    case "DATE":
                        date = _data.get("value", None)
                        if date:
                            date = datetime.strptime(date, "%d.%m.%y")
                        setattr(cls, item, date)

        for custom_key in custom_value:
            setattr(cls, custom_key, custom_value.get(custom_key, None))
        db.add(cls)
        db.commit()
        return cls

    def update_for_template(self, formData, db: Session):
        for item in formData:
            _type = formData[item].get("type")
            _data = formData[item]
            if (
                "VARCHAR" in _type
                or "TEXT" in _type
                or "FLOAT" in _type
                or "INTEGER" in _type
                or "HTML" in _type
                or "BIGINT" in _type
            ):
                setattr(self, item, _data.get("value", None))
            else:
                match _type:
                    case "SELEKT":
                        _isMulti = _data.get("isMulti", False)
                        if (
                            isinstance(_data.get("value", []), bool)
                            or _data.get("value", []) is None
                            or len(_data.get("value", [])) != 0
                        ):
                            if _isMulti:
                                model_relationship = []
                                for _item in _data.get("value", []):
                                    articles_class_ref = self.__mapper__.relationships[
                                        item
                                    ].entity.class_
                                    articles_class = articles_class_ref()
                                    for _model_key in _item:
                                        _model_value = _item[_model_key].get(
                                            "value", None
                                        )
                                        setattr(
                                            articles_class, _model_key, _model_value
                                        )
                                    model_relationship.append(articles_class)

                                    if isinstance(getattr(self, item, []), list):
                                        for old_item in getattr(self, item, []):
                                            db.delete(old_item)
                                        db.commit()
                                    setattr(self, item, model_relationship)
                            else:
                                mapper = inspect(self.__class__)
                                property = mapper.attrs[item]
                                if isinstance(property, RelationshipProperty):
                                    related_instances = [
                                        db.query(property.mapper.class_).get(id)
                                        for id in _data.get("value", [])
                                    ]
                                    setattr(self, item, related_instances)
                                elif isinstance(property, ColumnProperty):
                                    if isinstance(getattr(self, item, []), list):
                                        for old_item in getattr(self, item, []):
                                            db.delete(old_item)
                                        db.commit()
                                    setattr(
                                        self,
                                        item,
                                        (
                                            _data.get("value")
                                            if isinstance(_data.get("value", []), bool)
                                            or _data.get("value", []) is None
                                            else _data.get("value")[0]
                                        ),
                                    )
                        else:
                            mapper = inspect(self.__class__)
                            property = mapper.attrs[item]
                            if isinstance(property, RelationshipProperty):
                                setattr(self, item, [])
                            elif isinstance(property, ColumnProperty):
                                setattr(
                                    self,
                                    item,
                                    None,
                                )
                    case "MULTI":
                        model_relationship = []
                        for _item in _data.get("value", []):
                            articles_class_ref = self.__mapper__.relationships[
                                item
                            ].entity.class_
                            articles_class = articles_class_ref()
                            for _model_key in _item:
                                if (_item[_model_key].get("type", None)) == "MEDIA":
                                    _arrauItems = _item[_model_key].get("value", [])

                                    _model_value = None
                                    if len(_arrauItems) > 0:
                                        _arrauItem = _arrauItems[0].get("data", "")
                                        _model_value = _arrauItem
                                    if (
                                        not _model_value is None
                                        and not isinstance(_model_value, bool)
                                        and len(_model_value) == 0
                                    ):
                                        _model_value = None

                                elif (_item[_model_key].get("type", None)) == "SELEKT":

                                    _model_value = (
                                        False
                                        if isinstance(
                                            _item[_model_key].get("value", []), bool
                                        )
                                        else []
                                    )
                                    _isMulti = (
                                        _item[_model_key]
                                        .get("data", {})
                                        .get("isMulti", False)
                                    )
                                    if (
                                        isinstance(
                                            _item[_model_key].get("value", []), bool
                                        )
                                        or len(_item[_model_key].get("value", [])) != 0
                                    ):

                                        _model_relationship = []
                                        sub_model_relationship = []

                                        _articles_class = None

                                        articles_class_ref = (
                                            self.__mapper__.relationships[
                                                item
                                            ].entity.class_
                                        )
                                        if articles_class_ref:
                                            _articles_class = articles_class_ref()
                                            if (
                                                (_model_key)
                                                in _articles_class.__mapper__.relationships
                                            ):
                                                sub_articles_class = _articles_class.__mapper__.relationships[
                                                    _model_key
                                                ].entity.class_

                                        if _isMulti:
                                            for _item_value in _item[_model_key].get(
                                                "value", []
                                            ):
                                                if sub_articles_class:
                                                    item_value = db.query(
                                                        sub_articles_class
                                                    ).get(_item_value)
                                                    sub_model_relationship.append(
                                                        item_value
                                                    )
                                                elif articles_class:
                                                    item_value = db.query(
                                                        articles_class
                                                    ).get(_item_value)
                                                    _model_relationship.append(
                                                        item_value
                                                    )
                                            if len(sub_model_relationship) != 0:
                                                _model_value = sub_model_relationship
                                            else:
                                                _model_value = _model_relationship
                                        else:
                                            if (
                                                isinstance(
                                                    _item[_model_key].get("value", []),
                                                    list,
                                                )
                                                and len(
                                                    _item[_model_key].get("value", [])
                                                )
                                                > 0
                                            ):
                                                if sub_articles_class:
                                                    _model_value = [
                                                        db.query(
                                                            sub_articles_class
                                                        ).get(
                                                            _item[_model_key].get(
                                                                "value", []
                                                            )[0]
                                                        )
                                                    ]
                                                else:
                                                    _model_value = _item[
                                                        _item[_model_key].get(
                                                            "value", []
                                                        )[0]
                                                    ]
                                            else:
                                                _model_value = _item[_model_key].get(
                                                    "value", False
                                                )

                                else:
                                    _model_value = _item[_model_key].get("value", None)
                                if isinstance(
                                    getattr(articles_class, _model_key, []), list
                                ):
                                    for old_item in getattr(self, item, []):
                                        db.delete(old_item)
                                    db.commit()
                                setattr(articles_class, _model_key, _model_value)
                            model_relationship.append(articles_class)
                        if isinstance(getattr(self, item, []), list):
                            for old_item in getattr(self, item, []):
                                db.delete(old_item)
                            db.commit()
                        setattr(self, item, model_relationship)

                    case "MEDIA":

                        existing_model_relationship = getattr(self, item, [])
                        new_model_relationship = []
                        id_not_dell = []
                        articles_class_ref = self.__mapper__.relationships[
                            item
                        ].entity.class_

                        for _item in _data.get("value", []):
                            if _item.get("data", None) and not _item.get("id", None):
                                articles_class = articles_class_ref()
                                setattr(articles_class, "id", _item.get("id", None))
                                setattr(articles_class, "name", _item.get("name", None))
                                setattr(
                                    articles_class,
                                    "media",
                                    _item.get("data", None),
                                )
                                new_model_relationship.append(articles_class)
                            else:
                                id_not_dell.append(_item.get("id", None))

                        for old_item in existing_model_relationship:
                            if old_item.id in id_not_dell:
                                new_model_relationship.append(old_item)
                            else:
                                db.delete(old_item)

                        setattr(self, item, new_model_relationship)

                    case "DATETIME":
                        date = _data.get("value", None)
                        if date:
                            date = datetime.strptime(date, "%d.%m.%y %H:%M:%S")
                        setattr(self, item, date)
                    case "DATE":
                        date = _data.get("value", None)
                        if date:
                            date = datetime.strptime(date, "%d.%m.%y")
                        setattr(self, item, date)
        db.commit()
        return self

    @classmethod
    def get_value_class_noRp(cls, _object):
        """Класс создает шаблон для фронта из класса и заполненнго обьекта класса не учитывая внешние кючи

        Args:
            _object (_type_): _description_

        Returns:
            _type_: _description_
        """
        template = {}
        objects = vars(cls)
        mapper = inspect(cls)
        for _name in objects:
            if _name in mapper.attrs:
                name = mapper.attrs[_name]
                if not "id" in name.key:
                    if not isinstance(name, (RelationshipProperty)):
                        template[name.key] = {
                            "value": getattr(_object, name.key, ""),
                            "doc": (name.doc if name.doc else ""),
                            "type": str(name.columns[0].type),
                        }
        return template

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"

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
