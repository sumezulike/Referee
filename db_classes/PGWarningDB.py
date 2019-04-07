import asyncio
import logging
from typing import Dict, List
import asyncpg

from models.warnings_models import RefWarning
from config import warnings_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS warnings (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        mod_name VARCHAR,
        expiration_time TIMESTAMP NOT NULL,
        reason VARCHAR
        )
    """,
    """
    CREATE INDEX IF NOT EXISTS warnings_user_id_idx ON warnings (user_id);
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS warnings
    """,
)

logger = logging.getLogger("Referee")


# noinspection PyProtectedMember
class PGWarningDB:

    def __init__(self):
        self.pool = asyncpg.create_pool(
            host=warnings_config.PG_Host,
            database=warnings_config.PG_Database,
            user=warnings_config.PG_User,
            password=warnings_config.PG_Password
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

    async def put_warning(self, warning: RefWarning):
        """
        Save a warning into the db
        :param warning:
        """

        insert = (
            "INSERT into warnings(user_id, timestamp, mod_name, reason, expiration_time) VALUES($1, $2, $3, $4, $5)"
        )
        async with self.pool.acquire() as con:
            await con.execute(insert, warning.user_id, warning.timestamp, warning.mod_name, warning.reason, warning.expiration_time)

    async def get_warnings(self, user_id: int) -> List[RefWarning]:
        """
        Get a list of all logged warnings for a user
        :param user_id:
        :return:
        """
        query = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings WHERE user_id = $1"
        async with self.pool.acquire() as con:
            results = await con.fetch(query, user_id)

        warnings = [RefWarning(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            mod_name=row["mod_name"],
            reason=row["reason"],
            expiration_time=row["expiration_time"]
        ) for row in results]

        return warnings

    async def get_active_warnings(self, user_id: int):

        query = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings " \
                "WHERE user_id = $1 AND expiration_time > NOW()"

        async with self.pool.acquire() as con:
            results = await con.fetch(query, user_id)

        warnings = [RefWarning(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            mod_name=row["mod_name"],
            reason=row["reason"],
            expiration_time=row["expiration_time"]
        ) for row in results]

        return warnings

    async def get_all_warnings(self) -> Dict[str, List[RefWarning]]:
        warnings = {}

        query_all = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings ORDER BY user_id"

        async with self.pool.acquire() as con:
            results = await con.fetch(query_all)

        for row in results:
            w = RefWarning(
                user_id=row["user_id"],
                timestamp=row["timestamp"],
                mod_name=row["mod_name"],
                reason=row["reason"],
                expiration_time=row["expiration_time"]
            )
            if w.user_id not in warnings:
                warnings[w.user_id] = []
            warnings[w.user_id].append(w)

        return warnings

    async def get_all_active_warnings(self) -> Dict[int, List[RefWarning]]:

        warnings = {}

        query_all = """
        SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings 
        WHERE expiration_time > NOW() ORDER BY user_id
        """

        async with self.pool.acquire() as con:
            results = await con.fetch(query_all)

        for row in results:
            w = RefWarning(
                user_id=row["user_id"],
                timestamp=row["timestamp"],
                mod_name=row["mod_name"],
                reason=row["reason"],
                expiration_time=row["expiration_time"]
            )
            if w.user_id not in warnings:
                warnings[w.user_id] = []
            warnings[w.user_id].append(w)

        return warnings

    async def expire_warnings(self, user_id: int):
        query = "UPDATE warnings SET expiration_time = NOW() WHERE user_id = $1"

        async with self.pool.acquire() as con:
            await con.execute(query, user_id)
