from __future__ import annotations
from datetime import datetime

class HistoryMessage:

    def __init__(self, user_id: int, channel_id: int, timestamp: datetime, content: str):
        self.user_id = user_id
        self.channel_id = channel_id
        self.content = content
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.user_id, self.timestamp, self.channel_id, self.content))

    def __repr__(self):
        return str(self.__dict__)

    @property
    def timestamp_str(self):
        return self.timestamp.strftime("%b-%d-%Y %H:%M")

    @property
    def date_str(self):
        return self.timestamp.strftime("%b-%d-%Y")
