from __future__ import annotations

import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_protocol_initialize_list_and_call() -> None:
    async def run() -> set[str]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            env={**os.environ, "MCP_TRANSPORT": "stdio"},
        )
        async with (
            stdio_client(parameters) as streams,
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
        "get_route_stations",
    }
