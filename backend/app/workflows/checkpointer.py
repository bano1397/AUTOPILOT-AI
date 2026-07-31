"""LangGraph checkpointer lifecycle.

Owns the saver's connection explicitly — ``start()`` before use, ``stop()`` on
shutdown — so the application lifespan and tests control it rather than relying
on garbage collection. Graphs compiled with the saver persist their state per
``thread_id`` (the workflow run id), which is what makes the approval gate's
pause and resume work across requests.

**The backend follows the database.** On SQLite the checkpoint file lives on
local disk, which on a free PaaS tier is ephemeral: a restart loses every
paused run, and an approval sitting in review becomes unresumable. When
``DATABASE_URL`` points at Postgres, checkpoints go to Postgres too and survive
restarts and replicas. Deriving it from the existing URL rather than adding a
second setting means the two cannot drift into the state where the data is
durable and the checkpoints quietly are not.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.logging import get_logger

logger = get_logger("app.workflows.checkpointer")


def is_postgres(database_url: str) -> bool:
    return database_url.startswith(("postgresql", "postgres://"))


def to_psycopg_dsn(database_url: str) -> str:
    """Rewrite a SQLAlchemy async URL into the DSN psycopg expects.

    SQLAlchemy encodes its driver in the scheme (``postgresql+asyncpg://``);
    psycopg wants a plain ``postgresql://``. The checkpoint saver uses psycopg
    directly, so the driver suffix has to come off or the connection fails with
    an unhelpful scheme error.
    """
    dsn = database_url.split("+", 1)[0] + "://" + database_url.split("://", 1)[1]
    # asyncpg spells the TLS parameter `ssl`; libpq spells it `sslmode`.
    return dsn.replace("?ssl=require", "?sslmode=require")


class WorkflowCheckpointer:
    """Owns a LangGraph saver and its underlying connection.

    ``path`` is the SQLite file. Passing ``database_url`` for a Postgres
    instance switches the backend to Postgres and ignores the path.
    """

    def __init__(self, path: str, database_url: str | None = None) -> None:
        self._path = path
        self._database_url = database_url
        self._context: Any = None
        self.saver: Any = None

    @property
    def backend(self) -> str:
        """Which store checkpoints land in — reported by the readiness probe."""
        if self._database_url and is_postgres(self._database_url):
            return "postgres"
        return "sqlite"

    async def start(self) -> None:
        if self.saver is not None:
            return

        if self.backend == "postgres":
            assert self._database_url is not None  # noqa: S101 - narrowed by backend
            try:
                self._context = await self._postgres_context(self._database_url)
                self.saver = await self._context.__aenter__()
                await self.saver.setup()
                logger.info("checkpointer.started", extra={"backend": "postgres"})
                return
            except ImportError:
                # The extra is not installed. Falling back keeps the app
                # bootable, but paused runs will not survive a restart, so this
                # is a warning rather than a silent downgrade.
                logger.warning(
                    "checkpointer.postgres_unavailable",
                    extra={
                        "hint": "pip install 'langgraph-checkpoint-postgres'; "
                        "falling back to SQLite, checkpoints are not durable"
                    },
                )

        self._context = AsyncSqliteSaver.from_conn_string(self._path)
        self.saver = await self._context.__aenter__()
        logger.info("checkpointer.started", extra={"backend": "sqlite"})

    @staticmethod
    async def _postgres_context(database_url: str) -> Any:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return AsyncPostgresSaver.from_conn_string(to_psycopg_dsn(database_url))

    async def stop(self) -> None:
        if self._context is not None:
            await self._context.__aexit__(None, None, None)
            self._context = None
            self.saver = None
