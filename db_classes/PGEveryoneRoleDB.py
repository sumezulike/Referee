import asyncio
import logging
from datetime import datetime
from typing import List, Tuple

import asyncpg

from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS naughty_roles (
        user_id BIGINT PRIMARY KEY,
        time_given TIMESTAMP
        )
    """,
)

deletion = (
    """
    DROP TABLE IF EXISTS naughty_roles
    """,
)

logger = logging.getLogger("Referee")


class PGEveryoneRoleDB:
    def __init__(self):
        self.pool = asyncpg.create_pool(
            host=pg_config.PG_Host,
            database=pg_config.PG_Database,
            user=pg_config.PG_User,
            password=pg_config.PG_Password
        )

        asyncio.get_event_loop().run_until_complete(self.create_tables())

    async def close(self):
        """
        Closes the connection to the db
        """
        await self.pool.close()

    async def create_tables(self):
        """
        Creates the tables in the db if they don't exist.
        This is called on every startup
        """
        self.pool = await self.pool
        async with self.pool.acquire() as con:
            for query in creation:
                await con.execute(query)

    async def find_roles_given_before(self, before=None):
        if before is None:
            before = datetime.now()
        q = (
            "SELECT * FROM naughty_roles WHERE time_given <= $1"
        )
        async with self.pool.acquire() as con:
            results = await con.fetch(q, before)

        return [row["user_id"] for row in results]

    async def give_role(self, user):
        q = "INSERT INTO naughty_roles(user_id, time_given) VALUES($1, $2) ON CONFLICT (user_id) DO UPDATE SET time_given = EXCLUDED.time_given"

        async with self.pool.acquire() as con:
            await con.execute(q, user, datetime.now())

    async def remove_role(self, user):
        q = "DELETE FROM naughty_roles WHERE user_id=$1"

        async with self.pool.acquire() as con:
            await con.execute(q, user)
