import asyncio
import logging
import asyncpg

from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS aoc_users (
        discord_id BIGINT PRIMARY KEY,
        aoc_name VARCHAR UNIQUE
    )
    """,
    # bit clunky to have a separate table for this that'll only ever have 1 row, but whatever
    """
    CREATE TABLE IF NOT EXISTS aoc_cookie (
        cookie VARCHAR
    )
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS aoc_users
    """,
    """
    DROP TABLE IF EXISTS aoc_cookie
    """
)

logger = logging.getLogger("Referee")

class PGChristmasDB:
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


    async def update_cookie(self, cookie: str):
        delete = "DELETE FROM aoc_cookie"
        insert = "INSERT INTO aoc_cookie(cookie) VALUES ($1)"
        async with self.pool.acquire() as con:
            await con.execute(delete)
            await con.execute(insert, cookie)

    async def get_cookie(self):
        query = "SELECT * FROM aoc_cookie"
        async with self.pool.acquire() as con:
            results = await con.fetch(query)

        results = [r["cookie"] for r in results]

        return None if len(results) == 0 else results[0]


    async def add_user(self, aoc_name: str, discord_id: int):
        insert = (
            "INSERT into aoc_users(aoc_name, discord_id) VALUES($1, $2)"
        )
        async with self.pool.acquire() as con:
            await con.execute(insert, aoc_name, discord_id)

    async def update_user(self, aoc_name: str, discord_id: int):
        update = "UPDATE aoc_users SET aoc_name=$1 WHERE discord_id=$2"
        async with self.pool.acquire() as con:
            await con.execute(update, aoc_name, discord_id)

    async def get_all_users(self):
        query = "SELECT * FROM aoc_users"
        async with self.pool.acquire() as con:
            results = await con.fetch(query)

        return [(row["aoc_name"], row["discord_id"]) for row in results]

    async def get_user(self, aoc_name: str, discord_id: int):
        if aoc_name is None and discord_id is None:
            return None
        if aoc_name is not None and discord_id is not None:
            # wow very useful.
            # get_user("foo", 12345) == ("foo", 12345)
            return aoc_name, discord_id
        if aoc_name is None:
            # discord_id is not None, we want aoc_name
            query = "SELECT aoc_name, discord_id FROM aoc_users WHERE discord_id = $1"
        else:
            # aoc_name is not None, we want discord_id
            query = "SELECT aoc_name, discord_id FROM aoc_users WHERE aoc_name = $1"

        async with self.pool.acquire() as con:
            results = await con.fetch(query, discord_id if aoc_name is None else aoc_name)

        result = [(row["aoc_name"], row["discord_id"]) for row in results]
        if len(result) == 0:
            return None
        return result[0]
