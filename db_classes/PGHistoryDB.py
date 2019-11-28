import asyncio
import logging
from typing import List
import asyncpg

from config import history_config
from models.history_models import HistoryMessage

creation = (
    """
    CREATE TABLE IF NOT EXISTS history (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        channel_id BIGINT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        content VARCHAR NOT NULL
        )
    """,
    """
    CREATE INDEX IF NOT EXISTS history_user_id_idx ON history (user_id);
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS history
    """,
)

logger = logging.getLogger("Referee")


# noinspection PyProtectedMember
class PGHistoryDB:

    def __init__(self):
        self.pool = asyncpg.create_pool(
            host=history_config.PG_Host,
            database=history_config.PG_Database,
            user=history_config.PG_User,
            password=history_config.PG_Password
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

    async def put_message(self, message: HistoryMessage):
        """
        Save a message into the db
        :param message:
        """

        insert = (
            "INSERT into history(user_id, channel_id, timestamp, content) VALUES($1, $2, $3, $4)"
        )
        async with self.pool.acquire() as con:
            await con.execute(insert, message.user_id, message.channel_id, message.timestamp, message.content)

    async def get_messages(self, user_id: int) -> List[HistoryMessage]:
        """
        Get a list of all logged messages for a user
        :param user_id:
        :return:
        """
        query = "SELECT user_id, channel_id, timestamp, content FROM messages WHERE user_id = $1"
        async with self.pool.acquire() as con:
            results = await con.fetch(query, user_id)

        messages = [HistoryMessage(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            channel_id=row["channel_id"],
            content=row["content"]
        ) for row in results]

        return messages
