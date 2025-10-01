from __future__ import annotations

import os
from typing import Callable

import pytest
import pytest_asyncio

from cerbos.sdk.grpc.client import AsyncCerbosClient
from cerbos.sdk.model import Principal
from fastmcp.exceptions import McpError
from fastmcp.server.dependencies import AccessToken
from fastmcp.server.middleware import MiddlewareContext
from mcp.types import CallToolRequestParams, ListToolsRequest, Tool

from cerbos_fastmcp import CerbosAuthorizationMiddleware


def _make_access_token(role: str, region: str = "NA") -> AccessToken:
    return AccessToken(
        token="token",
        client_id="tester",
        scopes=["mcp:connect"],
        claims={
            "sub": "tester",
            "roles": [role],
            "department": role,
            "region": region,
        },
    )


async def _principal_builder(token: AccessToken) -> Principal:
    return Principal(
        id=token.claims["sub"],
        roles=token.claims.get("roles", []),
        attr={
            "department": token.claims.get("department", ""),
            "region": token.claims.get("region", ""),
        },
    )


@pytest.fixture
def run_with_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[AccessToken], None]:
    def _setter(token: AccessToken) -> None:
        monkeypatch.setattr(
            "cerbos_fastmcp.middleware.get_access_token",
            lambda: token,
        )

    return _setter


@pytest_asyncio.fixture
async def cerbos_client() -> AsyncCerbosClient:
    grpc_addr = os.environ.get("CERBOS_GRPC")
    if not grpc_addr:
        pytest.skip("CERBOS_GRPC not set. Run tests via `cerbos run -- pytest`.")

    client = AsyncCerbosClient(grpc_addr)
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_greet_allows_admin(
    cerbos_client: AsyncCerbosClient,
    run_with_access_token: Callable[[AccessToken], None],
) -> None:
    run_with_access_token(_make_access_token("ADMIN"))

    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=cerbos_client,
    )

    context = MiddlewareContext(
        message=CallToolRequestParams(name="greet", arguments={"name": "Alice"}),
        source="client",
    )

    async def call_next(_: MiddlewareContext[CallToolRequestParams]) -> str:
        return "OK"

    result = await middleware.on_call_tool(context, call_next)

    assert result == "OK"


@pytest.mark.asyncio
async def test_admin_tool_denied_for_sales(
    cerbos_client: AsyncCerbosClient,
    run_with_access_token: Callable[[AccessToken], None],
) -> None:
    run_with_access_token(_make_access_token("SALES"))

    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=cerbos_client,
    )

    context = MiddlewareContext(
        message=CallToolRequestParams(name="admin_tool", arguments={}),
        source="client",
    )

    async def call_next(_: MiddlewareContext[CallToolRequestParams]) -> str:
        return "OK"

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(context, call_next)

    assert exc_info.value.error.data == "cerbos_denied"


@pytest.mark.asyncio
async def test_list_tools_filters_using_pdp(
    cerbos_client: AsyncCerbosClient,
    run_with_access_token: Callable[[AccessToken], None],
) -> None:
    run_with_access_token(_make_access_token("SALES"))

    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=cerbos_client,
    )

    context = MiddlewareContext(message=ListToolsRequest(), source="client")

    tools = [
        Tool(
            name="greet",
            inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
        ),
        Tool(
            name="admin_tool",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_sales_data",
            inputSchema={
                "type": "object",
                "properties": {"region": {"type": "string"}},
            },
        ),
    ]

    async def call_next(_: MiddlewareContext[ListToolsRequest]) -> list[Tool]:
        return tools

    result = await middleware.on_list_tools(context, call_next)

    assert [tool.name for tool in result] == ["greet", "get_sales_data"]
