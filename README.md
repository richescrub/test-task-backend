Инстрокция

1. Создать файлик env с такими паррамтерами

```
# Dev server

POSTGRES_SERVER="localhost:54322"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="b48a36060fdca917362366c7a22212ce"
POSTGRES_DB="base_db"
base_url = postgresql://postgres:b48a36060fdca917362366c7a22212ce@localhost:54322/base_db
REDIS = "localhost"
```

2. Подня docker-compouse (файл бд ) в папке testD

3) poetry install ( если в системе нет poetry установить глобально ( почти все наши проекты используют его ))
4) npm run
5) npm run m (если есть node на пк ) иначе прочить в package.json
6) npm run u
7) npm run dev
8) Открыть в бразурере http://127.0.0.1:8001/


# Правила разработки

1) Все модели пишутся исключительно в папке model ( если сделать это вне то alimbic не найдет новые модели )
2) У моделей id всегда это **BigInteger** а название таблиц усказывать так __tablename__="user_User"  где **user** - Общий раздел а **User** названеи класса
3) Так же все функции для **api** писать в папке routs и регистрировать в файле main как в примере
   ```
   app.include_router(
       apply_decorator_to_router(form_router, header_api_key_auth(_router="forms")),
       prefix="/api/v1/forms",
       tags=["forms"],
   )
   ```

    Где  form_router это новый роутер Где  form_router новы роут а header_api_key_auth(_router="forms")  это какой раздел у ключа должен быть для доступа к этому роуту ( все ключи лежат в halpers/data_keys_Ayth)
