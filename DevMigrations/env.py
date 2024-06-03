import os
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from sqlalchemy.ext.declarative import DeclarativeMeta
import importlib
import os

load_dotenv()
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

base_url = os.environ.get("base_url")
config.set_main_option("sqlalchemy.url", base_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# all_models = []
# model_classes = [
#     getattr(models_QWE, attr)
#     for attr in dir(models_QWE)
#     if isinstance(getattr(models_QWE, attr), DeclarativeMeta)
# ]
# model_chats = [
#     getattr(messenger_models, attr)
#     for attr in dir(messenger_models)
#     if isinstance(getattr(messenger_models, attr), DeclarativeMeta)
# ]

# all_models.extend(model_classes)
# all_models.extend(model_chats)

model_classes = []

# Укажите путь к директории с файлами моделей
models_directory = "riche_questionnaire_back_end/models"

for filename in os.listdir(models_directory):
    if filename.endswith(".py"):
        module_name = filename[:-3]
        module = importlib.import_module(
            f"{models_directory.replace('/','.')}.{module_name}"
        )

        for attr in dir(module):
            attr_obj = getattr(module, attr)
            if isinstance(attr_obj, DeclarativeMeta):
                model_classes.append(attr_obj)

targets_metadata = [cls.metadata for cls in model_classes]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline(target_metadata) -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online(target_metadata) -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


for target_metadata in targets_metadata:
    if context.is_offline_mode():
        run_migrations_offline(target_metadata)
    else:
        run_migrations_online(target_metadata)
