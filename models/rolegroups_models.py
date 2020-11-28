from typing import Dict


class Rolegroup:

    def __init__(self, name: str, message_id: int = None, db_id: int = None):
        self.name: str = name
        self.message_id: int = message_id
        self.db_id: int = db_id
        self.roles: Dict[str: int] = dict()

    @property
    def emojis_by_role(self):
        return {v: k for k, v in self.roles.items()}

    def add_role(self, role_id: int, emoji: str):
        self.roles[emoji] = role_id

    def del_role(self, role_id: int = None, emoji: str = None):
        if emoji:
            self.roles.pop(emoji)
        elif role_id:
            self.roles.pop(self.emojis_by_role.get(role_id))

    def get_role(self, emoji: str):
        return self.roles.get(emoji)

    def get_emoji(self, role_id: int):
        return self.emojis_by_role.get(role_id, None)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.name, self.message_id))

    def __str__(self):
        return str(self.__dict__)
