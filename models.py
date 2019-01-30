import discord
import time
import abc


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
    def get_all_warnings(self) -> list:
        pass

    @abc.abstractmethod
    def delete_warnings(self, user: discord.User) -> int:
        pass

    @abc.abstractmethod
    def delete_all_warnings(self) -> int:
        pass
