from typing import List

import psycopg2

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
        self.conn: psycopg2._psycopg.connection = psycopg2.connect(
            host=modmail_config.PG_Host,
            database=modmail_config.PG_Database,
            user=modmail_config.PG_User,
            password=modmail_config.PG_Password
        )
        self.create_tables()

    def close(self):
        if not self.conn.closed:
            self.conn.close()

    def create_tables(self):
        cur: psycopg2._psycopg.cursor = self.conn.cursor()
        for command in creation:
            cur.execute(command)
        cur.close()
        self.conn.commit()

    def put_modmail(self, mail: ModMail) -> int:

        insert = """INSERT into modmail(author_id, author_name, timestamp, content, answer_count) 
                    VALUES(%s, %s, %s, %s, 0) RETURNING id
                 """
        cur = self.conn.cursor()

        cur.execute(insert, (mail.author_id, mail.author_name, mail.timestamp, mail.content))

        modmail_id = cur.fetchone()[0]
        mail.modmail_id = modmail_id

        cur.close()
        self.conn.commit()

        return modmail_id

    def assign_message_id(self, modmail_id: int, message_id: int):
        update = """UPDATE modmail SET message_id = %s WHERE id = %s"""
        cur = self.conn.cursor()

        cur.execute(update, (message_id, modmail_id))

        cur.close()

        self.conn.commit()
        return

    def put_answer(self, answer: ModMailAnswer) -> int:

        insert = """INSERT into answers(mod_id, mod_name, timestamp, content, modmail_id) 
                    VALUES(%s, %s, %s, %s, %s) RETURNING id
                 """
        cur = self.conn.cursor()

        cur.execute(insert,
                    (answer.mod_id, answer.mod_name, answer.timestamp, answer.content, answer.modmail.modmail_id))

        answer_id = cur.fetchone()[0]

        cur.close()
        self.conn.commit()

        self._put_modmailanswer(answer.modmail.modmail_id, answer_id)

        return answer_id

    def _put_modmailanswer(self, modmail_id: int, answer_id: int):

        insert = """INSERT into modmailanswers(modmail_id, answer_id) 
                    VALUES(%s, %s)
                 """
        cur = self.conn.cursor()

        cur.execute(insert, (modmail_id, answer_id))
        cur.close()
        self.conn.commit()

    def get_modmail(self, modmail_id: int) -> ModMail:
        query = "SELECT author_id, author_name, timestamp, content, answer_count, id, message_id FROM modmail " \
                "WHERE id = %s"
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(query, (modmail_id,))

        row = cur.fetchone()

        mail = ModMail(author_id=row[0], author_name=row[1], timestamp=row[2], content=row[3], answers=[],
                       modmail_id=row[5], message_id=row[6])
        if row[4] > 0:  # answers_count
            mail.answers = self.get_answers(mail)

        cur.close()
        self.conn.commit()
        return mail

    def get_latest_modmail(self) -> ModMail:
        query = "SELECT author_id, author_name, timestamp, content, answer_count, id, message_id FROM modmail " \
                "ORDER BY id DESC LIMIT 1"
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(query)

        row = cur.fetchone()

        mail = ModMail(author_id=row[0], author_name=row[1], timestamp=row[2], content=row[3], answers=[],
                       modmail_id=row[5], message_id=row[6])
        if row[4] > 0:  # answers_count
            mail.answers = self.get_answers(mail)

        cur.close()
        self.conn.commit()
        return mail

    def get_answers(self, modmail: ModMail) -> List[ModMailAnswer]:
        id_query = """SELECT answer_id from modmailanswers WHERE modmail_id = %s"""
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(id_query, (modmail.modmail_id,))

        answer_ids = [r[0] for r in cur.fetchall()]
        answers = [self.get_answer(a_id, modmail) for a_id in answer_ids]

        cur.close()
        return answers

    def get_answer(self, answer_id: int, modmail: ModMail = None) -> ModMailAnswer:

        query = "SELECT mod_id, mod_name, timestamp, content, modmail_id, id FROM answers WHERE id = %s"
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(query, (answer_id,))

        row = cur.fetchone()

        answer = ModMailAnswer(mod_id=row[0], mod_name=row[1], timestamp=row[2], content=row[3], modmail=modmail)

        if not modmail:
            modmail = self.get_modmail(row[4])
            answer.modmail = modmail

        cur.close()
        self.conn.commit()
        return answer

    def get_recent_modmail(self, limit):
        last_id_query = "SELECT id from modmail ORDER BY timestamp DESC LIMIT %s"

        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(last_id_query, (limit,))

        last_ids = [r[0] for r in cur.fetchall()]

        recent = [self.get_modmail(i) for i in last_ids]

        cur.close()

        return recent

    def get_unanswered_modmail(self, limit):
        id_query = "SELECT id from modmail WHERE answer_count != 0 LIMIT %s"

        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(id_query, (limit,))

        open_ids = [r[0] for r in cur.fetchall()]

        unanswered = [self.get_modmail(i) for i in open_ids]

        cur.close()

        return unanswered


if __name__ == "__main__":
    p = PGModMailDB()
    p.create_tables()
