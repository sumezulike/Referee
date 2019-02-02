from __future__ import annotations
import time


class Warning:

    def __init__(self, user_id: str, timestamp: float=time.time(), **kwargs):
        self.user_id = str(user_id)
        self.timestamp = timestamp

        self.reason = kwargs.pop("reason", "")
        self.expiration_time = kwargs.pop("expiration_time", None)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__


    def __ne__(self, other):
        return not self == other

    def is_expired(self):
        return self.expiration_time < time.time()

