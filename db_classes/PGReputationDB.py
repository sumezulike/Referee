import asyncio
import logging
import asyncpg
from config import reputation_config

creation = (
    # while this doesnt contain any new data, it's probably faster in the long run
    # to store the reputation than counting the number of results
    """
    CREATE TABLE IF NOT EXISTS reputation (
        user_id BIGINT PRIMARY KEY,
        current_rep INT NOT NULL,
        last_given TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS thanks (
        source_user BIGINT,
        target_user BIGINT,
        channel BIGINT,
        time TIMESTAMPTZ
    )
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS reputation
    """,
    """
    DROP TABLE IF EXISTS thanks
    """
)

logger = logging.getLogger("Referee")


# noinspection PyProtectedMember
class PGReputationDB:
    def __init__(self):
        self.pool = asyncpg.create_pool(
            host=reputation_config.PG_Host,
            database=reputation_config.PG_Database,
            user=reputation_config.PG_User,
            password=reputation_config.PG_Password
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

    async def update_last_given(self, user_id):
        """
        Tries to create a row with the user_id, and if one already exists,
        Updates their last_given column to NOW()
        """
        sql = "INSERT INTO reputation (user_id, current_rep, last_given) VALUES($1, 0, NOW()) ON CONFLICT (user_id) DO UPDATE SET last_given = NOW()"
        async with self.pool.acquire() as con:
            await con.execute(sql, user_id)

    async def get_user_rep(self, user_id):
        sql = "SELECT current_rep FROM reputation WHERE user_id = $1"

        async with self.pool.acquire() as con:
            results = await con.fetch(sql, user_id)

        return 0 if len(results) == 0 else results[0]["current_rep"]

    async def get_time_between_lg_now(self, user_id):
        sql = "SELECT EXTRACT(EPOCH FROM NOW() - last_given) AS diff FROM reputation WHERE user_id = $1"

        async with self.pool.acquire() as con:
            results = await con.fetch(sql, user_id)

        return None if not results else results[0]["diff"]

    async def thank(self, source, target, ch):
        await self.increment_reputation(target)
        await self.update_last_given(source)
        sql = "INSERT INTO thanks (source_user, target_user, channel, time) VALUES($1, $2, $3, NOW())"
        async with self.pool.acquire() as con:
            await con.execute(sql, source, target, ch)

    async def get_thanks_timeframe(self, since, until):
        sql = "SELECT * FROM thanks WHERE time >= $1 AND time <= $2"
        async with self.pool.acquire() as con:
            results = await con.fetch(sql, since, until)

        return results

    async def increment_reputation(self, user_id):
        sql = "INSERT INTO reputation (user_id, current_rep, last_given) VALUES($1, 1, null) ON CONFLICT " + \
              "(user_id) DO UPDATE SET current_rep = reputation.current_rep + 1"
        async with self.pool.acquire() as con:
            await con.execute(sql, user_id)

    async def get_leaderboard(self):
        sql = "SELECT user_id, current_rep FROM reputation ORDER BY current_rep DESC LIMIT $1"
        async with self.pool.acquire() as con:
            results = await con.fetch(sql, reputation_config.Leader_Limit)

        return results
