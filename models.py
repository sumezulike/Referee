from __future__ import annotations
from typing import List, Dict
import abc
import json
import time
import os


class WarningObj:

    def __init__(self, user_id: str, timestamp: float=time.time(), **kwargs):
        self.user_id = user_id
        self.timestamp = timestamp

        self.reason = kwargs.pop("reason", "")
        self.expiration_date = kwargs.pop("expiration_time", None)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__


    def __ne__(self, other):
        return not self == other

    def get_remaining_time(self):
        if not self.expiration_date:
            return self.timestamp         # It's weird, I know

        return self.expiration_date - time.time()

    def is_expired(self):
        return self.get_remaining_time() < 0


class WarningDB(abc.ABC):

    @abc.abstractmethod
    def __enter__(self) -> WarningDB:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        pass

    @abc.abstractmethod
    def put_warning(self, warning: WarningObj) -> WarningObj:
        pass

    @abc.abstractmethod
    def get_warnings(self, user_id: str) -> List[WarningObj]:
        pass

    @abc.abstractmethod
    def get_all_warnings(self) -> Dict[str, List[WarningObj]]:
        pass

    @abc.abstractmethod
    def delete_warnings(self, user_id: str) -> int:
        pass

    @abc.abstractmethod
    def delete_warning(self, warning: WarningObj):
        pass

    @abc.abstractmethod
    def delete_all_warnings(self) -> int:
        pass


def serialize_warning(warning: WarningObj) -> list:
    return [warning.user_id, warning.timestamp, warning.reason, warning.expiration_date]


def deserialize_warning(s_warning: list) -> WarningObj:
    return WarningObj(user_id=s_warning[0], timestamp=s_warning[1], message=s_warning[2], expiration_date=s_warning[3])


class JSONWarningDB(WarningDB):

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
        return True

    def put_warning(self, warning: WarningObj) -> WarningObj:
        s = serialize_warning(warning)
        if warning.user_id in self.data.keys():
            self.data[warning.user_id].append(s)
        else:
            self.data[warning.user_id] = [s]
        return deserialize_warning(s)

    def get_warnings(self, user_id: str) -> List[WarningObj]:
        return [deserialize_warning(w) for w in self.data.get(user_id, [])]

    def get_all_warnings(self) -> Dict[str, List[WarningObj]]:
        return {user_id: [deserialize_warning(w) for w in w_list] for user_id, w_list in self.data.items()}

    def delete_warning(self, warning: WarningObj):
        # TODO: implement
        pass

    def delete_warnings(self, user_id: str) -> int:
        count = len(self.data.get(user_id, []))
        self.data[user_id] = []
        return count

    def delete_all_warnings(self) -> int:
        count = sum([len(x) for x in self.data.values()])
        self.data = {}
        return count
