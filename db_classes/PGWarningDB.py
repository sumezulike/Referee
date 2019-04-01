import logging
from datetime import datetime
from typing import Dict, List
import psycopg2

from models.warnings_models import RefWarning
from config import warnings_config

creation = (
    """
    CREATE TABLE IF NOT EXISTS warnings (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        mod_name VARCHAR,
        expiration_time TIMESTAMP NOT NULL,
        reason VARCHAR
        )
    """,
    """
    CREATE INDEX IF NOT EXISTS warnings_user_id_idx ON warnings (user_id);
    """
)

deletion = (
    """
    DROP TABLE IF EXISTS warnings
    """,
)

logger = logging.getLogger("Referee")

# noinspection PyProtectedMember
class PGWarningDB:

    def __init__(self):
        self.conn: psycopg2._psycopg.connection = psycopg2.connect(
            host=warnings_config.PG_Host,
            database=warnings_config.PG_Database,
            user=warnings_config.PG_User,
            password=warnings_config.PG_Password
        )
        cur = self.conn.cursor()
        for query in creation:
            cur.execute(query)
        cur.close()

    def close(self):
        if not self.conn.closed:
            self.conn.close()

    def recreate_tables(self):
        cur: psycopg2._psycopg.cursor = self.conn.cursor()
        for command in creation:
            cur.execute(command)
        cur.close()
        self.conn.commit()

    def put_warning(self, warning: RefWarning):

        insert = "INSERT into warnings(user_id, timestamp, mod_name, reason, expiration_time) " \
                 "VALUES(%s, %s, %s, %s, %s)"
        cur = self.conn.cursor()

        cur.execute(insert,
                    (warning.user_id, warning.timestamp, warning.mod_name, warning.reason, warning.expiration_time))
        cur.close()
        self.conn.commit()

    def get_warnings(self, user_id: str) -> List[RefWarning]:
        query = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings WHERE user_id = %s"
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        cur.execute(query, (str(user_id),))

        results = cur.fetchall()

        cur.close()
        self.conn.commit()

        warnings = [RefWarning(*row) for row in results]

        return warnings

    def get_active_warnings(self, user_id: str):
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        query = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings " \
                "WHERE user_id = %s AND expiration_time > TIMESTAMP %s"

        cur.execute(query, (str(user_id), str(datetime.now())))

        results = cur.fetchall()

        warnings = [RefWarning(*row) for row in results]

        cur.close()

        logger.debug(str(warnings))

        return warnings

    def get_all_warnings(self) -> Dict[str, List[RefWarning]]:
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        query_ids = "SELECT DISTINCT user_id FROM warnings"
        cur.execute(query_ids)
        user_ids = cur.fetchall()

        warnings = {user_id[0]: [] for user_id in user_ids}

        query_all = "SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings ORDER BY user_id"

        cur.execute(query_all)

        results = cur.fetchall()

        for row in results:
            w = RefWarning(*row)
            warnings[row[1]].append(w)

        cur.close()

        return warnings

    def get_all_active_warnings(self) -> Dict[str, List[RefWarning]]:
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        warnings = {}

        query_all = """
        SELECT user_id, timestamp, mod_name, reason, expiration_time FROM warnings 
        WHERE expiration_time > TIMESTAMP %s ORDER BY user_id
        """

        cur.execute(query_all, (str(datetime.now()),))

        results = cur.fetchall()

        for row in results:
            w = RefWarning(*row)
            if w.user_id not in warnings:
                warnings[w.user_id] = []
            warnings[w.user_id].append(w)

        cur.close()

        return warnings

    def expire_warnings(self, user_id: str):
        cur: psycopg2._psycopg.cursor = self.conn.cursor()

        query = "UPDATE warnings SET expiration_time = TIMESTAMP %s WHERE user_id = %s"

        cur.execute(query, (datetime.now(), str(user_id)))

        cur.close()

        self.conn.commit()


if __name__ == "__main__":
    p = PGWarningDB()
    p.recreate_tables()
