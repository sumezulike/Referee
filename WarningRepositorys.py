from __future__ import annotations
from typing import List, Dict
import abc
import json
import os

from models import Warning


class WarningRepository(abc.ABC):

    @abc.abstractmethod
    def __enter__(self) -> WarningRepository:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        pass

    @abc.abstractmethod
    def put_warning(self, warning: Warning) -> Warning:
        pass

    @abc.abstractmethod
    def get_warnings(self, user_id: str) -> List[Warning]:
        pass

    @abc.abstractmethod
    def get_all_warnings(self) -> Dict[str, List[Warning]]:
        pass

    @abc.abstractmethod
    def delete_warnings(self, user_id: str) -> int:
        pass

    @abc.abstractmethod
    def delete_warning(self, warning: Warning):
        pass

    @abc.abstractmethod
    def delete_all_warnings(self) -> int:
        pass


def serialize_warning(warning: Warning) -> list:
    return [warning.user_id, warning.timestamp, warning.reason, warning.expiration_time]


def deserialize_warning(s_warning: list) -> Warning:
    return Warning(user_id=s_warning[0], timestamp=s_warning[1], reason=s_warning[2], expiration_time=s_warning[3])


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
        return True

    def put_warning(self, warning: Warning) -> Warning:
        s = serialize_warning(warning)
        if warning.user_id in self.data.keys():
            self.data[warning.user_id].append(s)
        else:
            self.data[warning.user_id] = [s]
        return deserialize_warning(s)

    def get_warnings(self, user_id: str) -> List[Warning]:
        user_id = str(user_id)
        return [deserialize_warning(w) for w in self.data.get(user_id, [])]

    def get_all_warnings(self) -> Dict[str, List[Warning]]:
        return {user_id: [deserialize_warning(w) for w in w_list] for user_id, w_list in self.data.items()}

    def delete_warning(self, warning: Warning):
        self.data[warning.user_id] = [w for w in self.data.get(warning.user_id, []) if deserialize_warning(w) != warning]
        if not self.data[warning.user_id]:
            del self.data[warning.user_id]

    def delete_warnings(self, user_id: str) -> int:
        user_id = str(user_id)
        count = len(self.data.get(user_id, []))
        self.data[user_id] = []
        return count

    def delete_all_warnings(self) -> int:
        count = sum([len(x) for x in self.data.values()])
        self.data = {}
        return count
