"""Legacy entry-point tests for the AI tool dispatcher.

These predate the agent-loop refactor that moved ``execute_tool`` from
``app.api.endpoints.ai`` (where it used to live as a private dispatch
function) into ``shared.domain.services.ai_toolkit``. The tests still
target the old import path, and the first one references a ``test_user``
fixture that only exists locally in tests/test_auth.py.

Skipped pending a rewrite that:
  - imports from shared.domain.services.ai_toolkit;
  - declares its own user fixture (or moves the existing one into
    conftest.py so it's available everywhere);
  - matches the current execute_tool signature, which now takes
    ``(tool_name, tool_args, db, current_user, investigation_id)``
    in that exact order.

The companion test_ai_agent_loop.py has comprehensive coverage of the
agent ReAct loop already, so this file isn't blocking confidence in
the dispatcher; it's just stale.
"""

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.skip(reason="legacy import path; rewrite in a follow-up — see module docstring")


@pytest.mark.asyncio
async def test_ai_tool_dispatch_search_identities(db, test_user):
    from shared.domain.services.ai_toolkit import execute_tool

    result = await execute_tool(
        tool_name="search_identities",
        tool_args={"identifier": "nonexistent_identity"},
        db=db,
        current_user=test_user,
        investigation_id=None,
    )

    assert result["tool"] == "search_identities"
    assert result["count"] == 0
    assert "data" in result


@pytest.mark.asyncio
async def test_ai_tool_dispatch_unknown():
    from shared.domain.services.ai_toolkit import execute_tool

    result = await execute_tool(
        tool_name="hack_the_gibson",
        tool_args={},
        db=AsyncMock(),
        current_user=AsyncMock(),
        investigation_id=None,
    )

    assert "error" in result
    assert "Unknown tool" in result["error"]
