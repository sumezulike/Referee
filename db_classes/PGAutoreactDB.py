import asyncio
import logging
import asyncpg
import discord

from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS autoreactions (
        id SERIAL PRIMARY KEY,
        regex VARCHAR,
        channel_id BIGINT,
        emoji VARCHAR
        )
    """,
)

deletion = (
    """
    DROP TABLE IF EXISTS autoreactions
    """,
)

logger = logging.getLogger("Referee")


# noinspection PyProtectedMember
class PGAutoreactDB:

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


    async def add_autoreaction(self, emoji: discord.Emoji, regex: str, channel_id: int = None):
        """
        Save an autoreaction instruction into the db
        """

        insert = (
            "INSERT into autoreactions(regex, channel_id, emoji) VALUES($1, $2, $3)"
        )
        async with self.pool.acquire() as con:
            await con.execute(insert, regex, channel_id, emoji)


    async def remove_autoreaction(self, autoreaction_id: int):
        """
        Remove a reaction instruction
        :param autoreaction_id: Primary key id from the db
        :return:
        """
        query = "DELETE FROM autoreactions WHERE id = $1"
        async with self.pool.acquire() as con:
            await con.execute(query, autoreaction_id)


    async def get_autoreactions_list(self):
        query_all = "SELECT id, regex, channel_id, emoji FROM autoreactions"

        async with self.pool.acquire() as con:
            results = await con.fetch(query_all)

        autoreactions = [dict(
            id=row["id"],
            regex=row["regex"],
            channel_id=row["channel_id"],
            emoji=row["emoji"])
            for row in results
        ]

        return autoreactions
