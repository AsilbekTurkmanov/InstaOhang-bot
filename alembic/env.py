import os
import sys
from logging.config import fileConfig

from alembic import context

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL

def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    import sqlalchemy as sa
    engine = sa.create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
