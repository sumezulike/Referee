import unittest
from models import JSONWarningDB, WarningObj
import time

DB_FILE = "tests.json"


class TestJSONWarningDB(unittest.TestCase):

    def setUp(self):
        with open(DB_FILE, "w") as file:
            file.write("{}")

    def test_with(self):
        with JSONWarningDB(filepath=DB_FILE) as db:
            pass

    def test_put_warning_return(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = WarningObj(user_id=user_id, reason=message)
        with JSONWarningDB(filepath=DB_FILE) as db:
            re_warning = db.put_warning(warning)
            self.assertEqual(warning, re_warning)

    def test_put_warning_get_warning(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = WarningObj(user_id=user_id, reason=message)
        with JSONWarningDB(filepath=DB_FILE) as db:
            db.put_warning(warning)
            re_warning = db.get_warnings(user_id=user_id)[0]
        self.assertEqual(warning, re_warning)


    def test_put_warning_get_warning_persistence(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = WarningObj(user_id=user_id, reason=message)
        with JSONWarningDB(filepath=DB_FILE) as db:
            db.put_warning(warning)

        with JSONWarningDB(filepath=DB_FILE) as db:
            re_warnings = db.get_warnings(user_id=user_id)
        self.assertTrue(re_warnings)
        self.assertEqual(warning, re_warnings[0])


if __name__ == '__main__':
    unittest.main()
