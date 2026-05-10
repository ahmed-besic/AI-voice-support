from datetime import datetime, timezone
from typing import Any

from .base import ToolAdapter, ToolSpec


class CreateSupportTicketAdapter(ToolAdapter):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name='create_support_ticket',
            description='Create a lightweight support ticket record for handoff or follow-up.',
            schema={
                'type': 'object',
                'properties': {
                    'subject': {'type': 'string'},
                    'description': {'type': 'string'},
                    'priority': {'type': 'string', 'enum': ['low', 'medium', 'high']},
                    'customerEmail': {'type': 'string'},
                },
                'required': ['subject', 'description'],
            },
        )

    async def execute(self, args: dict[str, Any], *, session_id: str, site_id: str) -> Any:
        return {
            'ticketId': f'tkt_{session_id[:8]}',
            'siteId': site_id,
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'subject': args.get('subject', 'Support request'),
            'priority': args.get('priority', 'medium'),
            'status': 'open',
        }
