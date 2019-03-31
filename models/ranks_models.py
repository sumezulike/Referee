
class Rank:

    def __init__(self, name: str, role_id: int = None, message_id: int = None):
        self.name = name
        self.role_id = role_id
        self.message_id = message_id

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.name, self.role_id, self.message_id))

    def __str__(self):
        return str(self.__dict__)
