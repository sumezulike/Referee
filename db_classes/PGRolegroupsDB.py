import asyncio
from typing import List

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

    async def add_rolegroup(self, rolegroup: Rolegroup) -> Rolegroup:
        """
        Inserts a rolegroup row into the db
        :param rolegroup: The new rolegroup_cmd object
        """

        insert = "INSERT into rolegroups(name, message_id) VALUES($1, $2) RETURNING id"
        async with self.pool.acquire() as con:
            res = await con.fetch(insert, rolegroup.name, rolegroup.message_id)
            rolegroup_id = res[0]["id"]
            rolegroup.db_id = rolegroup_id

        insert = "INSERT into rolegroup_roles(rolegroup_id, role_id, emoji) VALUES($1, $2, $3)"
        async with self.pool.acquire() as con:
            for emoji, role_id in rolegroup.roles.items():
                await con.execute(insert, rolegroup_id, role_id, emoji)

        return rolegroup

    async def update_rolegroup(self, rolegroup: Rolegroup) -> Rolegroup:
        """
        Updates an existing rolegroup
        :param rolegroup:
        :return:
        """
        old = await self.get_rolegroup(rolegroup_id=rolegroup.db_id)

        if old.name != rolegroup.name:
            update = f"UPDATE rolegroups SET name = $1 WHERE id = $2"
            async with self.pool.acquire() as con:
                await con.execute(update, rolegroup.name, rolegroup.db_id)
        old_roles = old.roles
        new_roles = rolegroup.roles

        remove = [x for x in old_roles.items() if x not in new_roles.items()]
        add = [x for x in new_roles.items() if x not in old_roles.items()]

        delete = f"DELETE FROM rolegroup_roles WHERE rolegroup_id=$1 AND emoji=$2"
        insert = f"INSERT into rolegroup_roles(rolegroup_id, role_id, emoji) VALUES($1, $2, $3)"
        async with self.pool.acquire() as con:
            for emoji, _ in remove:
                await con.execute(delete, rolegroup.db_id, emoji)

            for emoji, role_id in add:
                await con.execute(insert, rolegroup.db_id, role_id, emoji)

        return await self.get_rolegroup(rolegroup_id=rolegroup.db_id)

    async def get_rolegroup(self, rolegroup_id: int = None, message_id: int = None) -> Rolegroup:
        """
        This method looks up a rolegroup either by name or discord message ID
        :param id: The db id of the rolegroup selection message
        :return: The found and reconstructed Rolegroup object
        """
        if not rolegroup_id and not message_id:
            raise Exception("get_rolegroup called without arguments")

        query = f"SELECT id, name, message_id FROM rolegroups where {'id' if rolegroup_id else 'message_id'} = $1"

        async with self.pool.acquire() as con:
            result: asyncpg.Record = await con.fetchrow(query, rolegroup_id or message_id)

            if result:
                r = Rolegroup(name=result["name"], message_id=result["message_id"], db_id=result["id"])
                query = "SELECT role_id, emoji FROM rolegroup_roles where rolegroup_id = $1"
                rows: asyncpg.Record = await con.fetch(query, r.db_id)
                for row in rows:
                    r.add_role(role_id=row["role_id"], emoji=row["emoji"])
                return r

    async def delete_rolegroup(self, rolegroup_id: int):
        """
        Delete a rolegroup_cmd by discord role ID
        :param rolegroup_id:
        :param id: The db id of the rolegroup
        """
        query = "DELETE FROM rolegroups WHERE id = $1"

        async with self.pool.acquire() as con:
            await con.execute(query, rolegroup_id)
            query = "DELETE FROM rolegroup_roles WHERE rolegroup_id = $1"
            await con.execute(query, rolegroup_id)

    async def get_all_rolegroups(self) -> List[Rolegroup]:
        """
        Get all entries
        :return: List of Rolegroup objects
        """
        async with self.pool.acquire() as con:
            query = "SELECT id FROM rolegroups"

            rows = await con.fetch(query)
            return [await self.get_rolegroup(rolegroup_id=row["id"]) for row in rows]
