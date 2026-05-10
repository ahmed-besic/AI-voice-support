from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.repository import prune_stale_sessions


class DummyResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class DummySession:
    def __init__(self):
        self.executed = None
        self.committed = False

    async def execute(self, statement):
        self.executed = statement
        return DummyResult(2)

    async def commit(self):
        self.committed = True


def test_prune_stale_sessions_executes_delete():
    session = DummySession()

    async def run():
        deleted = await prune_stale_sessions(session, site_id='demo-site')
        return deleted

    import asyncio

    deleted = asyncio.run(run())
    assert deleted == 2
    assert session.executed is not None
    assert session.committed is True
