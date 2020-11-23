import asyncio
import asyncpg

from models.rolegroups_models import Rolegroup
from config.config import PostGres as pg_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS rolegroups (
        id SERIAL PRIMARY KEY,
        name VARCHAR UNIQUE NOT NULL,
        message_id BIGINT NOT NULL
        )
    """,
    """CREATE TABLE IF NOT EXISTS rolegroup_roles (
        rolegroup_id INTEGER NOT NULL,
        role_id BIGINT NOT NULL,
        emoji VARCHAR NOT NULL
    )
    """,
)

deletion = (
    """
    DROP TABLE IF EXISTS rolegroups
    """,
    """
    DROP TABLE IF EXISTS rolegroup_roles
    """,
)


# noinspection PyProtectedMember
class PGRolegroupsDB:

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

    async def add_rolegroup(self, rolegroup: Rolegroup):
        """
        Inserts a rolegroup row into the db
        :param rolegroup: The new rolegroup object
        """

        insert = "INSERT into rolegroups(name, message_id) " \
                 "VALUES($1, $2)"
        async with self.pool.acquire() as con:
            await con.execute(insert, rolegroup.name, rolegroup.message_id)

    async def get_rolegroup(self, name: str = None, message_id: int = None) -> Rolegroup:
        """
        This method looks up a rolegroup either by name or discord message ID
        :param name: The name of the rolegroup
        :param message_id: The discord id of the rolegroup selection message
        :return: The found and reconstructed Rolegroup object
        """
        if name is None and message_id is None:
            raise Exception("get_rolegroup called without arguments")

        if name:
            query = "SELECT name, message_id FROM rolegroups where name = $1"

        else:
            query = "SELECT name, message_id FROM rolegroups where message_id = $1"

        async with self.pool.acquire() as con:
            result: asyncpg.Record = await con.fetchrow(query, name or message_id)

            if result:
                r = Rolegroup(name=result["name"], message_id=result["message_id"])
                rolegroup_id = result["id"]
                query = "SELECT role_id, emoji FROM rolegroup_roles where rolegroup_id = $1"
                rows: asyncpg.Record = await con.fetch(query, rolegroup_id)
                for row in rows:
                    r.add_role(role_id=row["role_id"], emoji=row["emoji"])
                return r

    async def delete_rolegroup(self, name: str):
        """
        Delete a rolegroup by discord role ID
        :param name: The name of the rolegroup
        """
        query = "DELETE FROM rolegroups WHERE name = $1 RETURNING id"

        async with self.pool.acquire() as con:
            deleted_id = await con.fetch(query, name)["id"]
            query = "DELETE FROM rolegroup_roles WHERE rolegroup_id = $1"
            await con.execute(query, deleted_id)

    async def get_all_rolegroups(self):
        """
        Get all entries
        :return: List of Rolegroup objects
        """
        async with self.pool.acquire() as con:
            query = "SELECT message_id FROM rolegroups"

            rows = await con.fetch(query)
            return [self.get_rolegroup(message_id=row["message_id"]) for row in rows]
