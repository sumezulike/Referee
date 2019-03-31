import psycopg2

from models.ranks_models import Rank
from config import ranks_config

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
        self.conn: psycopg2._psycopg.connection = psycopg2.connect(
            host=ranks_config.PG_Host,
            database=ranks_config.PG_Database,
            user=ranks_config.PG_User,
            password=ranks_config.PG_Password
        )
        cur = self.conn.cursor()
        for query in creation:
            cur.execute(query)
        cur.close()

    def close(self):
        if not self.conn.closed:
            self.conn.close()

    def create_tables(self):
        cur: psycopg2._psycopg.cursor = self.conn.cursor()
        for command in creation:
            cur.execute(command)
        cur.close()
        self.conn.commit()

    def add_rank(self, rank: Rank):

        insert = "INSERT into ranks(name, role_id, message_id) " \
                 "VALUES(%s, %s, %s)"
        cur = self.conn.cursor()

        cur.execute(insert, (rank.name, rank.role_id, rank.message_id))
        cur.close()
        self.conn.commit()

    def get_rank(self, role_id: int = None, name: str = None, message_id: int = None) -> Rank:
        if role_id is None and name is None and message_id is None:
            raise RuntimeError("get_rank called without arguments")

        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        if role_id:
            query = "SELECT name, role_id, message_id FROM ranks where role_id = %s"

        elif name:
            query = "SELECT name, role_id, message_id FROM ranks where name = %s"

        else:  # message_id
            query = "SELECT name, role_id, message_id FROM ranks where message_id = %s"

        cur.execute(query, (role_id or name or message_id,))
        result = Rank(*cur.fetchone())
        cur.close()
        return result

    def delete_rank(self, role_id: int):
        query = "DELETE FROM ranks WHERE role_id = %s"
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(query, (role_id,))

        cur.close()
        self.conn.commit()


if __name__ == "__main__":
    p = PGRanksDB()
    p.create_tables()
