from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_ai_tool_dispatch_search_identities(db, test_user):
    from app.api.endpoints.ai import execute_tool

    # Execute the tool with mocked inputs
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
    from app.api.endpoints.ai import execute_tool

    # Execute a tool that does not exist
    result = await execute_tool(
        tool_name="hack_the_gibson", tool_args={}, db=AsyncMock(), current_user=AsyncMock(), investigation_id=None
    )

    assert "error" in result
    assert "Unknown tool" in result["error"]
