from __future__ import annotations
from typing import List, Dict
import abc


class WarningRepository(abc.ABC):

    @abc.abstractmethod
    def __enter__(self) -> WarningRepository:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        pass

    @abc.abstractmethod
    def put_warning(self, warning: Warning) -> Warning:
        pass

    @abc.abstractmethod
    def get_warnings(self, user_id: str) -> List[Warning]:
        pass

    @abc.abstractmethod
    def get_all_warnings(self) -> Dict[str, List[Warning]]:
        pass

    @abc.abstractmethod
    def delete_warnings(self, user_id: str) -> int:
        pass

    @abc.abstractmethod
    def delete_warning(self, warning: Warning):
        pass

    @abc.abstractmethod
    def delete_all_warnings(self) -> int:
        pass
