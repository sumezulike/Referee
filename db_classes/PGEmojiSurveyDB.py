import asyncio
import logging
from typing import List, Tuple

import asyncpg
import discord

from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS emojisurvey (
        message_id BIGINT PRIMARY KEY,
        emoji VARCHAR
        )
    """,
)

deletion = (
    """
    DROP TABLE IF EXISTS emojisurvey
    """,
)

logger = logging.getLogger("Referee")


# noinspection PyProtectedMember
class PGEmojiSurveyDB:

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


    async def add_message(self, message_id: int, emoji: str):

        insert = (
            "INSERT into emojisurvey(message_id, emoji) VALUES($1, $2)"
        )
        async with self.pool.acquire() as con:
            await con.execute(insert, message_id, emoji)


    async def get_all(self) -> List[Tuple[int, str]]:
        query_all = "SELECT message_id, emoji FROM emojisurvey"

        async with self.pool.acquire() as con:
            results = await con.fetch(query_all)

        messages = [(row["message_id"], row["emoji"]) for row in results]

        return messages

    async def delete_message(self, message_id: int):
        """
        Remove a reaction instruction
        :param autoreaction_id: Primary key id from the db
        :return:
        """
        query = "DELETE FROM emojisurvey WHERE message_id = $1"
        async with self.pool.acquire() as con:
            await con.execute(query, message_id)
