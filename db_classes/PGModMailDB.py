import asyncio
from typing import List

import asyncpg

from config import modmail_config
from models.modmail_models import ModMail, ModMailAnswer

creation = (
    """
    CREATE TABLE IF NOT EXISTS modmail (
        id SERIAL PRIMARY KEY NOT NULL,
        author_id BIGINT NOT NULL,
        author_name VARCHAR NOT NULL ,
        timestamp TIMESTAMP NOT NULL,
        content TEXT NOT NULL ,
        answer_count INTEGER,
        message_id BIGINT
        )
    """,
    """
    CREATE TABLE IF NOT EXISTS answers (
        id SERIAL PRIMARY KEY,
        mod_id BIGINT NOT NULL,
        mod_name VARCHAR NOT NULL ,
        timestamp TIMESTAMP NOT NULL,
        content TEXT NOT NULL ,
        modmail_id BIGINT NOT NULL 
        )
    """,
    """
    CREATE TABLE IF NOT EXISTS modmailanswers (
        id SERIAL PRIMARY KEY NOT NULL,
        modmail_id INTEGER NOT NULL,
        answer_id INTEGER NOT NULL
        )
    """,

    """
    CREATE INDEX IF NOT EXISTS modmail_id_idx ON modmailanswers (modmail_id);
    """,

    """
    CREATE INDEX IF NOT EXISTS answer_id_idx ON modmailanswers (answer_id);
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS modmail
    """,
    """
    DROP TABLE IF EXISTS answers
    """,
    """
    DROP TABLE IF EXISTS modmailanswers
    """
)


# noinspection PyProtectedMember
class PGModMailDB:

    def __init__(self):
        self.pool = asyncpg.create_pool(
            host=modmail_config.PG_Host,
            database=modmail_config.PG_Database,
            user=modmail_config.PG_User,
            password=modmail_config.PG_Password
        )
        asyncio.get_event_loop().run_until_complete(self.create_tables())

    async def close(self):
        await self.pool.close()

    async def create_tables(self):
        async with self.pool.acquire() as con:
            for command in creation:
                con.execute(command)

    async def put_modmail(self, mail: ModMail) -> int:
        insert = """INSERT into modmail(author_id, author_name, timestamp, content, answer_count) 
                    VALUES(%s, %s, %s, %s, 0) RETURNING id
                 """
        async with self.pool.acquire() as con:
            row = con.fetchone(insert, (mail.author_id, mail.author_name, mail.timestamp, mail.content))

        mail.modmail_id = row["id"]
        return mail.modmail_id

    async def assign_message_id(self, modmail_id: int, message_id: int):
        update = """UPDATE modmail SET message_id = %s WHERE id = %s"""
        async with self.pool.acquire() as con:
            con.execute(update, (message_id, modmail_id))

    async def put_answer(self, answer: ModMailAnswer) -> int:
        insert = """INSERT into answers(mod_id, mod_name, timestamp, content, modmail_id) 
                    VALUES(%s, %s, %s, %s, %s) RETURNING id
                 """
        async with self.pool.acquire() as con:
            answer_id = con.fetchone(insert,
                                     (answer.mod_id, answer.mod_name, answer.timestamp, answer.content,
                                      answer.modmail.modmail_id)
                                     )

        await self._put_modmailanswer(answer.modmail.modmail_id, answer_id)
        return answer_id

    async def _put_modmailanswer(self, modmail_id: int, answer_id: int):
        insert = """INSERT into modmailanswers(modmail_id, answer_id) 
                    VALUES(%s, %s)
                 """
        async with self.pool.acquire() as con:
            con.execute(insert, (modmail_id, answer_id))

    async def get_modmail(self, modmail_id: int) -> ModMail:
        query = "SELECT author_id, author_name, timestamp, content, id, message_id, answer_count FROM modmail " \
                "WHERE id = %s"
        async with self.pool.acquire() as con:
            row = con.fetchone(query, (modmail_id,))

        mail = ModMail(author_id=row["author_id"], author_name=row["author_name"], timestamp=row["timestamp"], content=row["content"], answers=[],
                       modmail_id=row["id"], message_id=row["message_id"])
        if row["answer_count"] > 0:  # answers_count
            mail.answers = self.get_answers(mail)

        return mail

    async def get_latest_modmail(self) -> ModMail:
        query = "SELECT author_id, author_name, timestamp, content, id, message_id, answer_count FROM modmail " \
                "ORDER BY id DESC LIMIT 1"
        async with self.pool.acquire() as con:
            row = con.fetchone(query)

        mail = ModMail(author_id=row["author_id"], author_name=row["author_name"], timestamp=row["timestamp"], content=row["content"], answers=[],
                       modmail_id=row["id"], message_id=row["message_id"])
        if row["answer_count"] > 0:  # answers_count
            mail.answers = self.get_answers(mail)

        return mail

    async def get_answers(self, modmail: ModMail) -> List[ModMailAnswer]:
        id_query = """SELECT answer_id from modmailanswers WHERE modmail_id = %s"""
        async with self.pool.acquire() as con:
            rows = con.fetch(id_query, (modmail.modmail_id,))

        answer_ids = [r["answer_id"] for r in rows]
        answers = [await self.get_answer(a_id, modmail) for a_id in answer_ids]

        return answers

    async def get_answer(self, answer_id: int, modmail: ModMail = None) -> ModMailAnswer:
        query = "SELECT mod_id, mod_name, timestamp, content, modmail_id, id FROM answers WHERE id = %s"
        async with self.pool.acquire() as con:
            row = con.fetchone(query, (answer_id,))

        answer = ModMailAnswer(mod_id=row["mod_id"], mod_name=row["mod_name"], timestamp=row["timestamp"], content=row["content"], modmail=modmail)

        if not modmail:
            modmail = await self.get_modmail(row["modmail_id"])
            answer.modmail = modmail

        return answer
