from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from config import settings
from models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compares the database against these tables.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # `alembic upgrade head --sql` prints the SQL instead of running it.
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # A separate engine from the app's: no pool needed for a one-off command.
    engine = create_engine(settings.database_url, poolclass=pool.NullPool)

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
