from datetime import datetime


class Thank:

    def __init__(self, source_user_id: int, target_user_id: int, channel_id: int, message_id: int, timestamp: datetime,
                 server_id: int = 0):
        self.source_user_id = source_user_id
        self.target_user_id = target_user_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.server_id = server_id
        self.timestamp = timestamp

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.source_user_id, self.target_user_id, self.message_id))

    def __repr__(self):
        return str(self.__dict__)

