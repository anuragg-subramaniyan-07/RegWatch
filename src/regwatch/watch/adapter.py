from abc import ABC, abstractmethod

from regwatch.models import Reference


class SourceAdapter(ABC):
    @abstractmethod
    def get_new_references(self, last_seen_id: int) -> list[Reference]:
        ...
