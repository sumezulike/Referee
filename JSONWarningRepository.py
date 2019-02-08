from typing import List, Dict
import json
import os

from abstract.WarningRepository import WarningRepository
from models.refwarning import RefWarning


def serialize_warning(warning: RefWarning) -> list:
    return [warning.user_id, warning.timestamp, warning.reason, warning.expiration_time]


def deserialize_warning(s_warning: list) -> RefWarning:
    return RefWarning(user_id=s_warning[0], timestamp=s_warning[1], reason=s_warning[2], expiration_time=s_warning[3])


class JSONWarningRepository(WarningRepository):

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: Dict[str, List[list]] = {}

    def __enter__(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as file:
                file.write("{}")
                self.data = {}
        else:
            with open(self.filepath, "r") as file:
                content = file.read()
                if len(content) == 0:
                    self.data = {}
                else:
                    self.data = json.loads(content)

        if not isinstance(self.data, dict):
            raise RuntimeError("Malformed database")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with open(self.filepath, "w") as file:
            json.dump(self.data, file)
        return False

    def put_warning(self, warning: RefWarning) -> RefWarning:
        s = serialize_warning(warning)
        if warning.user_id in self.data.keys():
            self.data[warning.user_id].append(s)
        else:
            self.data[warning.user_id] = [s]
        return deserialize_warning(s)

    def get_warnings(self, user_id: str) -> List[RefWarning]:
        user_id = str(user_id)
        return [deserialize_warning(w) for w in self.data.get(user_id, [])]

    def get_all_warnings(self) -> Dict[str, List[RefWarning]]:
        return {user_id: [deserialize_warning(w) for w in w_list] for user_id, w_list in self.data.items()}

    def delete_warning(self, warning: RefWarning):
        self.data[warning.user_id] = [w for w in self.data.get(warning.user_id, []) if deserialize_warning(w) != warning]
        if not self.data[warning.user_id]:
            del self.data[warning.user_id]

    def delete_warnings(self, user_id: str) -> int:
        user_id = str(user_id)
        count = len(self.data.get(user_id, []))
        del self.data[user_id]
        return count

    def delete_all_warnings(self) -> int:
        count = sum([len(x) for x in self.data.values()])
        self.data = {}
        return count
