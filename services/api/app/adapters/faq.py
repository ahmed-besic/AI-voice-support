from typing import Any

from sqlalchemy import select

from ..database import SessionLocal
from ..models import KnowledgeEntry
from .base import KnowledgeAdapter, ToolAdapter, ToolSpec


class FAQSearchAdapter(ToolAdapter, KnowledgeAdapter):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name='faq_search',
            description='Search the support FAQ knowledge base for concise answers.',
            schema={
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'The support question to search for.'},
                },
                'required': ['query'],
            },
        )

    async def search(self, query: str, site_id: str) -> list[dict[str, Any]]:
        async with SessionLocal() as session:
            entries = (
                await session.scalars(select(KnowledgeEntry).where(KnowledgeEntry.site_id == site_id))
            ).all()
        return rank_entries(query, entries)

    async def execute(self, args: dict[str, Any], *, session_id: str, site_id: str) -> Any:
        query = str(args.get('query', '')).strip()
        results = await self.search(query, site_id)
        return {'results': results, 'sessionId': session_id, 'siteId': site_id}


def rank_entries(query: str, entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
    lowered = query.lower()
    scored = []
    for entry in entries:
        haystack = f'{entry.title} {entry.content}'.lower()
        score = sum(1 for token in lowered.split() if token in haystack)
        scored.append(
            (
                score,
                {
                    'id': entry.id,
                    'title': entry.title,
                    'content': entry.content,
                    'source': entry.source,
                    'metadata': entry.metadata_json,
                },
            )
        )
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for score, entry in scored if score > 0][:3]
