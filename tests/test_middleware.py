from __future__ import annotations

from typing import Iterable

import pytest

from cerbos.sdk.model import Principal, Resource
from fastmcp.exceptions import McpError
from fastmcp.server.dependencies import AccessToken
from fastmcp.server.middleware import MiddlewareContext
from mcp.types import CallToolRequestParams, ListToolsRequest, Tool

from cerbos_fastmcp import CerbosAuthorizationMiddleware


class DummyClient:
    def __init__(self, allowed_actions: Iterable[str]) -> None:
        self.allowed_actions = set(allowed_actions)
        self.calls: list[tuple[str, Principal, Resource]] = []

    async def is_allowed(
        self, action: str, principal: Principal, resource: Resource
    ) -> bool:
        self.calls.append((action, principal, resource))
        return action in self.allowed_actions

    async def close(self) -> None:  # pragma: no cover - compatibility shim
        return None


@pytest.fixture
def access_token() -> AccessToken:
    return AccessToken(
        token="token",
        client_id="tester",
        scopes=["mcp:connect"],
        claims={
            "sub": "tester",
            "roles": ["ADMIN"],
            "department": "engineering",
            "region": "NA",
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


@pytest.mark.asyncio
async def test_tool_call_allowed(
    monkeypatch: pytest.MonkeyPatch, access_token: AccessToken
) -> None:
    monkeypatch.setattr(
        "cerbos_fastmcp.middleware.get_access_token",
        lambda: access_token,
    )

    client = DummyClient({"tools/call::greet"})
    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=client,
    )

    context = MiddlewareContext(
        message=CallToolRequestParams(name="greet", arguments={"name": "Alice"})
    )

    async def call_next(_: MiddlewareContext[CallToolRequestParams]) -> str:
        return "OK"

    result = await middleware.on_call_tool(context, call_next)

    assert result == "OK"
    assert client.calls and client.calls[0][0] == "tools/call::greet"


@pytest.mark.asyncio
async def test_tool_call_denied(
    monkeypatch: pytest.MonkeyPatch, access_token: AccessToken
) -> None:
    monkeypatch.setattr(
        "cerbos_fastmcp.middleware.get_access_token",
        lambda: access_token,
    )

    client = DummyClient(set())
    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=client,
    )

    context = MiddlewareContext(
        message=CallToolRequestParams(name="greet", arguments={"name": "Alice"})
    )

    async def call_next(_: MiddlewareContext[CallToolRequestParams]) -> str:
        return "OK"

    with pytest.raises(McpError) as exc:
        await middleware.on_call_tool(context, call_next)

    assert exc.value.error.data == "cerbos_denied"
    assert client.calls and client.calls[0][0] == "tools/call::greet"


@pytest.mark.asyncio
async def test_list_tools_filters_denied_items(
    monkeypatch: pytest.MonkeyPatch, access_token: AccessToken
) -> None:
    monkeypatch.setattr(
        "cerbos_fastmcp.middleware.get_access_token",
        lambda: access_token,
    )

    client = DummyClient({"tools/list", "tools/list::greet"})
    middleware = CerbosAuthorizationMiddleware(
        principal_builder=_principal_builder,
        cerbos_client=client,
    )

    context = MiddlewareContext(message=ListToolsRequest())

    tools = [
        Tool(
            name="greet",
            inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
        ),
        Tool(
            name="admin_tool",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]

    async def call_next(_: MiddlewareContext[ListToolsRequest]) -> list[Tool]:
        return tools

    result = await middleware.on_list_tools(context, call_next)

    assert [tool.name for tool in result] == ["greet"]
    assert {call[0] for call in client.calls} == {
        "tools/list",
        "tools/list::greet",
        "tools/list::admin_tool",
    }
