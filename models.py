import discord
import abc
import json
import os


class WarningDB(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __enter__(self):
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abc.abstractmethod
    def get_warnings(self, user: discord.User) -> list:
        pass

    @abc.abstractmethod
    def get_all_warnings(self) -> dict:
        pass

    @abc.abstractmethod
    def delete_warnings(self, user: discord.User) -> int:
        pass

    @abc.abstractmethod
    def delete_all_warnings(self) -> int:
        pass


class JSONWarningDB(WarningDB):

    def __init__(self, filepath: str, **kwargs):
        self.filepath = filepath
        self.file = None
        self.data = {}

    def __enter__(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as file:
                file.write("{}")
        self.file = open(self.filepath, "w")
        self.data = json.load(self.file)
        if not isinstance(self.data, dict):
            raise RuntimeError("Invalid form")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        json.dump(self.data, self.file)
        self.file.close()

    def get_warnings(self, user: discord.User) -> list:
        return self.data.get(user.id, [])

    def get_all_warnings(self) -> dict:
        return self.data

    def delete_warnings(self, user: discord.User) -> int:
        count = len(self.data.get(user.id, []))
        self.data[user.id] = []
        return count

    def delete_all_warnings(self) -> int:
        count = sum([len(x) for x in self.data.values()])
        self.data = {}
        return count

