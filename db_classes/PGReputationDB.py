import asyncio
import logging
import asyncpg
from config import reputation_config
from models.reputation_models import Thank
from datetime import datetime, timedelta

creation = (
    """
    CREATE TABLE IF NOT EXISTS thanks (
        source_user_id BIGINT,
        target_user_id BIGINT,
        channel_id BIGINT,
        message_id BIGINT,
        time TIMESTAMPTZ
    )
    """,
)

deletion = (
    """
    DROP TABLE IF EXISTS thanks
    """,
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

        # number of reputation -> array of functions with two arguments (user id, server_id)
        self.callbacks = {}

        asyncio.get_event_loop().run_until_complete(self.create_tables())

    def add_callback(self, rep_amount, callback):
        if rep_amount not in self.callbacks:
            self.callbacks[rep_amount] = []
        self.callbacks[rep_amount].append(callback)


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


    async def get_user_rep(self, user_id, since=datetime(day=1, month=1, year=2000), until=None):
        if not until:
            until = datetime.now()
        sql = "SELECT COUNT(*) FROM thanks WHERE target_user_id = $1 and time >= $2 and time <= $3"

        async with self.pool.acquire() as con:
            results = await con.fetch(sql, user_id, since, until)

        return results[0][0]


    async def add_thank(self, new_thank: Thank):
        sql = "INSERT INTO thanks (source_user_id, target_user_id, channel_id, message_id, time) VALUES($1, $2, $3, $4, $5)"
        async with self.pool.acquire() as con:
            await con.execute(sql, new_thank.source_user_id, new_thank.target_user_id, new_thank.channel_id,
                              new_thank.message_id, new_thank.timestamp)
            if len(self.callbacks) != 0:
                thank_amount = await self.get_user_rep(new_thank.target_user_id)
                if thank_amount in self.callbacks:
                    for callback in self.callbacks[thank_amount]:
                        await callback(new_thank.target_user_id, new_thank.server_id)


    async def get_thanks(self, since=datetime(day=1, month=1, year=2000), until=None):
        if not until:
            until = datetime.now()
        sql = "SELECT * FROM thanks WHERE time >= $1 AND time <= $2"
        async with self.pool.acquire() as con:
            results = [Thank(source_user_id=r["source_user_id"], target_user_id=r["target_user_id"],
                             channel_id=r["channel_id"], message_id=r["message_id"], timestamp=r["time"])
                       for r in await con.fetch(sql, since, until)]

        return results

    async def get_leaderboard(self, since=datetime(day=1, month=1, year=2000), until=None):
        if not until:
            until = datetime.now()
        thanks = await self.get_thanks(since, until)
        if not thanks:
            return []

        member_scores = {user_id: [t.target_user_id for t in thanks].count(user_id) for user_id in set(t.target_user_id for t in thanks)}
        sorted_user_ids = sorted(member_scores, key=member_scores.get, reverse=True)
        ranked_scores = {score: i + 1 for i, score in enumerate(sorted(set(member_scores.values()), reverse=True))}
        leaderboard = [{"user_id": user_id, "score": member_scores.get(user_id), "rank": ranked_scores.get(member_scores.get(user_id))} for user_id in sorted_user_ids]

        return leaderboard
