from __future__ import annotations
from datetime import datetime
from typing import List


class ModMail:

    def __init__(self, author_id: int, author_name: str, timestamp: datetime, content: str,
                 answers: List[ModMailAnswer] = None, modmail_id: int = None, message_id: int = None):
        self.author_id = author_id
        self.author_name = author_name
        self.timestamp = timestamp
        self.content = content
        self.answers = answers
        self.modmail_id = modmail_id
        self.message_id = message_id

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.author_id, self.timestamp, self.content, self.answers, self.modmail_id))

    def __str__(self):
        return f"ModMail '{self.modmail_id}' (From: {self.author_name}({self.author_id}), {self.timestamp_str}: {self.content})"

    @property
    def timestamp_str(self):
        return self.timestamp.strftime("%b-%d-%Y %H:%M")

    @property
    def date_str(self):
        return self.timestamp.strftime("%b-%d-%Y")


class ModMailAnswer:

    def __init__(self, mod_id: str, mod_name: str, timestamp: datetime, content: str, modmail: ModMail):
        self.mod_id = mod_id
        self.mod_name = mod_name
        self.timestamp = timestamp
        self.content = content
        self.modmail = modmail

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.mod_id, self.timestamp, self.content))

    def __str__(self):
        return f"ModMailAnswer(By {self.mod_name} to {self.modmail.author_name}), {self.timestamp_str}: {self.content})"

    @property
    def timestamp_str(self):
        return self.timestamp.strftime("%b %d %Y %H:%M")

    @property
    def date_str(self):
        return self.timestamp.strftime("%b-%d-%Y")
