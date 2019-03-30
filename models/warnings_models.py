from __future__ import annotations
from datetime import datetime


class RefWarning:
    NEVER = datetime(9999, 1, 1)

    def __init__(self, user_id: int, timestamp: datetime, mod_name: str, reason: str = "",
                 expiration_time: datetime = NEVER):
        self.user_id = user_id
        self.timestamp = timestamp
        self.mod_name = mod_name
        self.reason = reason
        self.expiration_time = expiration_time

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.user_id, self.timestamp, self.reason, self.expiration_time))

    def __repr__(self):
        return str(self.__dict__)

    @property
    def timestamp_str(self):
        return self.timestamp.strftime("%b-%d-%Y %H:%M")

    @property
    def date_str(self):
        return self.timestamp.strftime("%b-%d-%Y")

    @property
    def expiration_str(self):
        return self.expiration_time.strftime("%b-%d-%Y %H:%M")

    @property
    def expiration_date_str(self):
        return self.expiration_time.strftime("%b-%d-%Y")

    def is_expired(self):
        return self.expiration_time < datetime.now()
