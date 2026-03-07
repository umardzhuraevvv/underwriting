import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, text
from sqlalchemy import pool

from alembic import context

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем модели чтобы Alembic видел метадату
from app.database import Base, DATABASE_URL

# Устанавливаем URL из переменной окружения / database.py
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Target metadata для autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Set lock timeout to avoid hanging on locked alembic_version table
        dialect_name = connection.dialect.name
        if dialect_name == "postgresql":
            connection.execute(text("SET lock_timeout = '10s'"))
            connection.execute(text("SET statement_timeout = '25s'"))

        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
