from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]


class ToolAdapter(ABC):
    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, args: dict[str, Any], *, session_id: str, site_id: str) -> Any:
        raise NotImplementedError


class KnowledgeAdapter(ABC):
    @abstractmethod
    async def search(self, query: str, site_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError
