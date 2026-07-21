from __future__ import annotations

import os

import anyio
import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("MCP_TEST_URL"),
        reason="Set MCP_TEST_URL to run the container MCP protocol smoke test.",
    ),
]


def test_container_mcp_initialize_and_tools() -> None:
    async def run() -> set[str]:
        headers = {}
        if token := os.getenv("MCP_AUTH_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        async with (
            httpx.AsyncClient(headers=headers) as http_client,
            streamable_http_client(os.environ["MCP_TEST_URL"], http_client=http_client) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            call_result = await session.call_tool("find_stations", {"query": "x"})
            assert call_result.isError is True
            return {tool.name for tool in tools.tools}

    assert anyio.run(run) == {
        "search_tickets",
        "find_stations",
        "get_carriages",
        "get_train_availability",
        "get_minimal_prices",
        "get_car_scheme",
        "get_car_images",
        "get_route_stations",
    }
