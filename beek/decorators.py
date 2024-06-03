import asyncio
import base64
import datetime
from functools import wraps
import inspect
from typing import Callable, Union
from fastapi import HTTPException, Header, Request
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm.session import Session
from beek.db import getRedis
import pickle
from fastapi.responses import JSONResponse, StreamingResponse
from .halpers import data_keys_Ayth, decode_access_token
import time
import logging


def modify_func_signature(
    func, new_param_name="HeaderApiKey", default_value=Header(None)
):
    sig = inspect.signature(func)
    if new_param_name not in sig.parameters:
        new_param = inspect.Parameter(
            name=new_param_name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=default_value,
        )
        new_params = list(sig.parameters.values()) + [new_param]
        func.__signature__ = sig.replace(parameters=new_params)
    return func


def useCallback(useredis=True, time_live: Union[int, None] = None, radel="default"):
    """Функция хеширования вычислений функций

    Args:
        useredis (bool, optional): Использовать redis или кеш питона. Defaults to True.
        time_live (Union[int, None], optional): Время жизни (работает только с redis). Defaults to None.
        radel (str, optional): Уникайльный кючь для того ,что бы *args, **kwargs не накладывались друг на друга. Defaults to "default".
    """

    cache = getRedis() if useredis else {}

    def cashFunc(func):
        @wraps(func)
        async def wrapperAsunc(*args, **kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Session)]
            filtered_kwargs = {
                key: value
                for key, value in kwargs.items()
                if not isinstance(value, Session)
            }

            if "HeaderApiKey" in filtered_kwargs:
                del filtered_kwargs["HeaderApiKey"]
            key = (radel, tuple(filtered_args), frozenset(filtered_kwargs.items()))

            if useredis:
                data = cache.get(base64.b64encode(pickle.dumps(key)).decode("utf-8"))
                if data is None:
                    result = await func(*args, **kwargs)
                    cache.set(
                        base64.b64encode(pickle.dumps(key)).decode("utf-8"),
                        base64.b64encode(pickle.dumps(result)).decode("utf-8"),
                        ex=time_live if time_live else None,
                    )
                    return result
                else:
                    return pickle.loads(base64.b64decode(data))
            else:
                if key in cache:
                    return cache[key]

                result = await func(*args, **kwargs)

                cache[key] = result
                return result

        @wraps(func)
        def wrapper(*args, **kwargs):
            filtered_args = [arg for arg in args if not isinstance(arg, Session)]
            filtered_kwargs = {
                key: value
                for key, value in kwargs.items()
                if not isinstance(value, Session)
            }
            if "HeaderApiKey" in filtered_kwargs:
                del filtered_kwargs["HeaderApiKey"]
            key = (radel, tuple(filtered_args), frozenset(filtered_kwargs.items()))

            if useredis:
                data = cache.get(base64.b64encode(pickle.dumps(key)).decode("utf-8"))
                if data is None:
                    result = func(*args, **kwargs)

                    cache.set(
                        base64.b64encode(pickle.dumps(key)).decode("utf-8"),
                        base64.b64encode(pickle.dumps(result)).decode("utf-8"),
                        ex=time_live if time_live else None,
                    )
                    return result
                else:
                    return pickle.loads(base64.b64decode(data))
            else:
                if key in cache:
                    return cache[key]

                result = func(*args, **kwargs)

                cache[key] = result
                return result

        if asyncio.iscoroutinefunction(func):
            return wrapperAsunc
        else:
            return wrapper

    return cashFunc


def chek_no_photo(func):
    func = header_api_key_auth(False)(func)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if result is None:
            default_image_path = "no-image-icon.png"
            with open(default_image_path, "rb") as img_file:
                try:
                    return StreamingResponse(
                        iter([img_file.read()]), media_type="image/jpeg"
                    )
                except Exception as e:
                    return None
        return result

    return wrapper


# def run_in_parallel(func, **kvargs):
#     @wraps(func)
#     async def wrapper(*args, **kwargs):
#         def process_request():
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)

#             async def data_func():
#                 if inspect.iscoroutinefunction(func):
#                     return await func(*args, **kwargs)
#                 else:
#                     return func(*args, **kwargs)

#             return loop.run_until_complete(data_func())

#         loop = asyncio.get_running_loop()
#         result = await loop.run_in_executor(None, process_request)
#         return result

#     return wrapper


def run_in_parallel(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        if inspect.iscoroutinefunction(func):
            future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
            return await asyncio.wrap_future(future)
        else:
            return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper


def sync_to_async(func, *args, **kwargs):
    """
    Запускает асинхронную функцию в отдельном потоке, обходя ограничение на запуск циклов событий.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, func(*args, **kwargs))
        return future.result()


def header_api_key_auth(_router=None):
    """
    Декоратор для добаления ключа авторизации в запрос

    Если парраметр _router не передан то будет 500 ошибка
    Если _router == False то проверка отключается

    Проверяет доступо по ключу из запроса в базе (временной) data_keys_Ayth

    Декоратор можно задать сразу всем роутам в файле main.py
    ( ws исключаются ) и если нужно выборочно отключить

    app.include_router(
        apply_decorator_to_router(
            test_router, header_api_key_auth(_router="test_router")
        ),
        prefix="/test",
        ...
    )

    Можно повысить уровень доступа или отключить проверку в конкретной функции
    Для этого нудно применить напрямую у функции ( пример отключения проверки)

    @test.get("/test")
    @header_api_key_auth(_router=False)
    async def test():

    Не влияет на useCallback тк парраметр HeaderApiKey удаляется и не попадает в саму функцию
    """

    def decorator(func):

        if hasattr(func, "_is_decorated") and func._is_decorated:
            return func

        func = run_in_parallel(func)
        func = modify_func_signature(func)
        func = timerWorkLogger(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = kwargs.get("HeaderApiKey", None)

            if _router is None:
                return JSONResponse(
                    content={
                        "data": "Небыл передан раздел",
                    },
                    status_code=500,
                )
            if _router == False:
                del kwargs["HeaderApiKey"]
                return await func(*args, **kwargs)

            if key is None:
                return JSONResponse(
                    content={
                        "data": "Небыл передан ключь",
                    },
                    status_code=401,
                )

            isGWT, *_args = decode_access_token(key)
            if isGWT:
                del kwargs["HeaderApiKey"]
                return await func(*args, **kwargs)

            if not key in data_keys_Ayth:
                return JSONResponse(
                    content={
                        "data": "Не авторизован",
                    },
                    status_code=401,
                )

            if "__all__" in data_keys_Ayth[key]:
                del kwargs["HeaderApiKey"]
                return await func(*args, **kwargs)

            if not _router in data_keys_Ayth[key]:
                return JSONResponse(
                    content={
                        "data": "Нет прав доступа",
                    },
                    status_code=401,
                )
            del kwargs["HeaderApiKey"]
            return await func(*args, **kwargs)

        wrapper._is_decorated = True
        return wrapper

    return decorator


def timerWorkLogger(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logging.basicConfig(level=logging.INFO)
        start_time = time.time()
        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:

            result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        execution_time_formatted = str(datetime.timedelta(seconds=execution_time))
        message = f"[ + ] Функция {func.__name__} выполнилась за {execution_time_formatted} секунд"
        logging.info(message)
        return result

    return wrapper
