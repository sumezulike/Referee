import asyncio
import asyncpg

from models.ranks_models import Rank
from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS ranks (
        id SERIAL PRIMARY KEY,
        name VARCHAR UNIQUE NOT NULL,
        role_id BIGINT NOT NULL,
        message_id BIGINT NOT NULL
        )
    """,
    """
    CREATE INDEX IF NOT EXISTS ranks_message_id_idx ON ranks (message_id);
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS ranks
    """,
)


# noinspection PyProtectedMember
class PGRanksDB:

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

    async def add_rank(self, rank: Rank):
        """
        Inserts a rank row into the db
        :param rank: The new rank object that
        """

        insert = "INSERT into ranks(name, role_id, message_id) " \
                 "VALUES($1, $2, $3)"
        async with self.pool.acquire() as con:
            await con.execute(insert, rank.name, rank.role_id, rank.message_id)

    async def get_rank(self, role_id: int = None, name: str = None, message_id: int = None) -> Rank:
        """
        This method looks up a rank either by discord role ID, name or discord message ID
        :param role_id: Discord id of the ranks role
        :param name: The name of the rank
        :param message_id: The discord id of the ranks selection message
        :return: The found and reconstructed Rank object
        """
        if role_id is None and name is None and message_id is None:
            raise RuntimeError("get_rank called without arguments")

        if role_id:
            query = "SELECT name, role_id, message_id FROM ranks where role_id = $1"

        elif name:
            query = "SELECT name, role_id, message_id FROM ranks where name = $1"

        else:  # message_id
            query = "SELECT name, role_id, message_id FROM ranks where message_id = $1"

        async with self.pool.acquire() as con:
            result: asyncpg.Record = await con.fetchrow(query, role_id or name or message_id)

        if result:
            return Rank(name=result["name"], role_id=result["role_id"], message_id=result["message_id"])

    async def delete_rank(self, role_id: int):
        """
        Delete a rank by discord role ID
        :param role_id: The ID of the role connected to the rank
        """
        query = "DELETE FROM ranks WHERE role_id = $1"

        async with self.pool.acquire() as con:
            await con.execute(query, role_id)

    async def get_all_ranks(self):
        """
        Get all entries
        :return: List of ranks
        """
        async with self.pool.acquire() as con:
            query = "SELECT name, role_id, message_id FROM ranks"

            rows = await con.fetch(query)
            return [Rank(name=row["name"], role_id=row["role_id"], message_id=row["message_id"]) for row in rows]
