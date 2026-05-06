from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extensions

from .config import Config, load_config
from .logger import get_logger

logger = get_logger(__name__)


@contextmanager
def get_connection(
    config: Config | None = None,
) -> Generator[psycopg2.extensions.connection, None, None]:
    cfg = config or load_config()
    conn: psycopg2.extensions.connection | None = None
    try:
        conn = psycopg2.connect(
            host=cfg.postgres_host,
            port=cfg.postgres_port,
            dbname=cfg.postgres_db,
            user=cfg.postgres_user,
            password=cfg.postgres_password,
        )
        yield conn
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.error("database_error", error=str(exc), exc_info=True)
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_cursor(
    config: Config | None = None,
) -> Generator[psycopg2.extensions.cursor, None, None]:
    with get_connection(config) as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
