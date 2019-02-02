import unittest
from JSONWarningRepository import JSONWarningRepository
from models.warning import Warning
import time
import os

DB_FILE = "tests.json"


class TestJSONWarningDB(unittest.TestCase):

    def setUp(self):
        with open(DB_FILE, "w") as file:
            file.write("{}")

    def test_with(self):
        with JSONWarningRepository(filepath=DB_FILE) as db:
            pass

    def test_file_not_existant(self):
        filename = str(time.time())
        warning = Warning(user_id=filename)
        with JSONWarningRepository(filepath=filename) as db:
            db.put_warning(warning)

        with JSONWarningRepository(filepath=filename) as db:
            re_warning = db.get_warnings(filename)[0]

        self.assertEqual(warning, re_warning)

        os.remove(filename)

    def test_file_empty(self):
        filename = str(time.time())

        open(filename, "w").close()

        warning = Warning(user_id=filename)
        with JSONWarningRepository(filepath=filename) as db:
            db.put_warning(warning)

        with JSONWarningRepository(filepath=filename) as db:
            re_warning = db.get_warnings(filename)[0]

        self.assertEqual(warning, re_warning)

        os.remove(filename)

    def test_put_warning_return(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = Warning(user_id=user_id, reason=message)
        with JSONWarningRepository(filepath=DB_FILE) as db:
            re_warning = db.put_warning(warning)
            self.assertEqual(warning, re_warning)

    def test_put_warning_get_warning(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = Warning(user_id=user_id, reason=message)
        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.put_warning(warning)
            re_warning = db.get_warnings(user_id=user_id)[0]
        self.assertEqual(warning, re_warning)


    def test_put_warning_get_warning_persistence(self):
        user_id = "123456789"
        message = "Hello. My name is Inigo Montoya."

        warning = Warning(user_id=user_id, reason=message)
        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.put_warning(warning)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            re_warnings = db.get_warnings(user_id=user_id)
        self.assertTrue(re_warnings)
        self.assertEqual(warning, re_warnings[0])

    def test_delete_warning(self):
        user_1 = "123"
        user_2 = "456"
        user_3 = "789"

        warning_1 = Warning(user_id=user_1)
        warning_2 = Warning(user_id=user_2)
        warning_3 = Warning(user_id=user_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.put_warning(warning_1)
            db.put_warning(warning_2)
            db.put_warning(warning_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.delete_warning(warning_1)
            self.assertNotIn(warning_1, db.get_all_warnings())
            self.assertIn(warning_2, db.get_all_warnings())
            self.assertIn(warning_3, db.get_all_warnings())

    def test_delete_warnings(self):
        user_1 = "123"
        user_2 = "456"
        user_3 = "789"

        warning_1 = Warning(user_id=user_1)
        warning_2 = Warning(user_id=user_2)
        warning_3 = Warning(user_id=user_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.put_warning(warning_1)
            db.put_warning(warning_1)
            db.put_warning(warning_2)
            db.put_warning(warning_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.delete_warnings(user_1)
            self.assertNotIn(warning_1, db.get_all_warnings())
            self.assertIn(warning_2, db.get_all_warnings())
            self.assertIn(warning_3, db.get_all_warnings())

    def test_delete_all_warnings(self):
        user_1 = "123"
        user_2 = "456"
        user_3 = "789"

        warning_1 = Warning(user_id=user_1)
        warning_2 = Warning(user_id=user_2)
        warning_3 = Warning(user_id=user_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.put_warning(warning_1)
            db.put_warning(warning_1)
            db.put_warning(warning_2)
            db.put_warning(warning_3)

        with JSONWarningRepository(filepath=DB_FILE) as db:
            db.delete_all_warnings()
            self.assertFalse(db.get_all_warnings())


if __name__ == '__main__':
    unittest.main()
