from typing import Any

from .base import ToolAdapter
from .faq import FAQSearchAdapter
from .tickets import CreateSupportTicketAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {
            'faq_search': FAQSearchAdapter(),
            'create_support_ticket': CreateSupportTicketAdapter(),
        }

    def list_tool_descriptors(self, enabled_names: list[str]) -> list[dict[str, str]]:
        descriptors = []
        for name in enabled_names:
            adapter = self._adapters.get(name)
            if adapter:
                descriptors.append({'name': adapter.spec.name, 'description': adapter.spec.description})
        return descriptors

    def list_live_tool_declarations(self, enabled_names: list[str]) -> list[dict[str, Any]]:
        declarations = []
        for name in enabled_names:
            adapter = self._adapters.get(name)
            if adapter:
                declarations.append(
                    {
                        'name': adapter.spec.name,
                        'description': adapter.spec.description,
                        'parameters': adapter.spec.schema,
                    }
                )
        return declarations

    def get(self, name: str) -> ToolAdapter | None:
        return self._adapters.get(name)

    def faq_adapter(self) -> FAQSearchAdapter:
        adapter = self._adapters['faq_search']
        assert isinstance(adapter, FAQSearchAdapter)
        return adapter
