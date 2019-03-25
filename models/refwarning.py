from __future__ import annotations
from datetime import datetime


class RefWarning:

    NEVER = datetime(9999, 1, 1)

    def __init__(self, user_id: str, timestamp: datetime, **kwargs):
        self.user_id = str(user_id)
        self.timestamp = timestamp

        self.reason = kwargs.pop("reason", "")
        self.expiration_time = kwargs.pop("expiration_time", self.NEVER)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.user_id, self.timestamp, self.reason, self.expiration_time))

    def __str__(self):
        return "RefWarning(User_id: '{}', {} - {}, Reason: {})".format(self.user_id, self.timestamp, self.expiration_time, self.reason or "No reason")

    def is_expired(self):
        return self.expiration_time < datetime.now()
