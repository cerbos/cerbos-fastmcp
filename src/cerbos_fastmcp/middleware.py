"""Cerbos authorization middleware for FastMCP."""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, Awaitable, Callable, Optional
from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.grpc.client import AsyncCerbosClient
from cerbos.sdk.model import Principal, Resource
from fastmcp.server.dependencies import AccessToken, get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool
from fastmcp.utilities import logging
from google.protobuf import struct_pb2
from mcp import McpError
from mcp.types import (
    CallToolRequestParams,
    ErrorData,
    ListToolsRequest,
)


logger = logging.get_logger("cerbos_middleware")

PrincipalBuilder = Callable[
    [AccessToken],
    Awaitable[Principal] | Principal,
]


class CerbosAuthorizationMiddleware(Middleware):
    """Authorize MCP tool calls using Cerbos policies."""

    def __init__(
        self,
        cerbos_host: Optional[str] = None,
        *,
        principal_builder: PrincipalBuilder,
        cerbos_client: Optional[AsyncCerbosClient] = None,
        resource_kind: Optional[str] = None,
        tls_verify: Optional[bool | str] = None,
    ) -> None:
        super().__init__()

        if principal_builder is None:
            raise ValueError("principal_builder must be provided")

        self._principal_builder = principal_builder
        self._cerbos_host = cerbos_host or os.getenv("CERBOS_HOST")
        if cerbos_client is None and self._cerbos_host is None:
            raise ValueError(
                "cerbos_host must be provided or CERBOS_HOST environment variable must be set"
            )

        self._resource_kind = resource_kind or os.getenv(
            "CERBOS_RESOURCE_KIND", "mcp_server"
        )

        self._tls_verify = (
            tls_verify
            if tls_verify is not None
            else _env_tls("CERBOS_TLS_VERIFY", False)
        )

        # Defer client creation until first use so the gRPC channel binds to the running loop
        if cerbos_client is not None:
            self._client = cerbos_client
            self._owns_client = False
        else:
            # Lazily create the client in the active event loop to avoid loop mismatches
            self._client = None
            self._owns_client = True

        self._client_lock = asyncio.Lock()

    async def on_initialize(self, context, call_next):
        if self._owns_client:
            client = await self._ensure_client()
            if hasattr(client, "server_info"):
                await client.server_info()

        await call_next(context)

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, list[str]],
    ) -> Any:
        logger.info("Calling tool with Cerbos authorization")
        principal = await self._resolve_principal()
        if principal is None:
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="missing_principal",
                )
            )

        message = context.message
        tool_name = message.name
        arguments = message.arguments or {}

        action = f"tools/call::{tool_name}"
        resource = Resource(
            id=tool_name,
            kind=self._resource_kind,
            attr={
                "tool_name": tool_name,
                "arguments": arguments,
                "source": context.source,
            },
        )

        granted = await self._is_allowed(action, principal, resource)
        if not granted:
            logger.info(
                "Cerbos denied action",
                extra={
                    "principal": principal.id,
                    "action": action,
                    "resource": resource.id,
                },
            )
            raise McpError(
                ErrorData(code=-32010, message="Unauthorized",
                          data="cerbos_denied")
            )

        logger.debug(
            "Cerbos authorized tool call",
            extra={"principal": principal.id, "action": action},
        )
        return await call_next(context)

    async def on_list_tools(
        self,
        context: MiddlewareContext[ListToolsRequest],
        call_next: CallNext[ListToolsRequest, list[Tool]],
    ) -> list[Tool]:
        logger.info("Listing tools with Cerbos authorization")
        try:
            await self._authorize_command("tools/list")
        except McpError:
            return []

        original_result = await call_next(context)
        principal = await self._resolve_principal()
        if principal is None:
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="missing_principal",
                )
            )

        authorized_tools = []
        for tool in original_result:
            action = f"tools/list::{tool.name}"
            resource = Resource(
                id=tool.name,
                kind=self._resource_kind,
                attr={
                    "tool_name": tool.name,
                    "arguments": {},
                    "source": context.source,
                },
            )
            if await self._is_allowed(action, principal, resource):
                authorized_tools.append(tool)
            else:
                logger.info(
                    "Cerbos denied action",
                    extra={
                        "principal": principal.id,
                        "action": action,
                        "resource": resource.id,
                    },
                )
        return authorized_tools

    async def on_list_resources(self, context, call_next):
        logger.info("Listing resources with Cerbos authorization")
        try:
            await self._authorize_command("resources/list")
        except McpError:
            return []

        return await call_next(context)

    async def on_list_prompts(self, context, call_next):
        logger.info("Listing prompts with Cerbos authorization")
        try:
            await self._authorize_command("prompts/list")
        except McpError:
            return []

        return await call_next(context)

    async def _authorize_command(self, command_name: str) -> None:
        logger.info(f"Authorizing command: {command_name}")
        principal = await self._resolve_principal()
        if principal is None:
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="missing_principal",
                )
            )

        resource = Resource(id=command_name, kind=self._resource_kind)

        granted = await self._is_allowed(command_name, principal, resource)
        if not granted:
            logger.info(
                "Cerbos denied action",
                extra={
                    "principal": principal.id,
                    "action": command_name,
                    "resource": resource.id,
                },
            )
            raise McpError(
                ErrorData(code=-32010, message="Unauthorized",
                          data="cerbos_denied")
            )

        logger.debug(
            "Cerbos authorized command call",
            extra={
                "principal": principal.id,
                "resource": resource.id,
                "action": command_name,
            },
        )

    async def _is_allowed(
        self, action: str, principal: Principal, resource: Resource
    ) -> bool:
        logger.info(
            f"Authorizing action '{action}' for principal '{principal.id}' on resource kind:'{resource.kind} id:'{resource.id}'"
        )
        try:
            client = await self._ensure_client()
            principal_pb = _principal_to_proto(principal)
            resource_pb = _resource_to_proto(resource)
            return await client.is_allowed(action, principal_pb, resource_pb)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Cerbos authorization failed", exc_info=exc)
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="cerbos_error",
                )
            ) from exc

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.close()
            self._client = None

    async def _ensure_client(self) -> AsyncCerbosClient:
        if self._client is not None:
            return self._client

        if not self._owns_client:
            raise RuntimeError(
                "Cerbos client was provided but is not available")

        async with self._client_lock:
            if self._client is None:
                if not self._cerbos_host:
                    raise RuntimeError("Cerbos host is not configured")
                self._client = AsyncCerbosClient(
                    self._cerbos_host,
                    tls_verify=self._tls_verify,
                )
            return self._client

    async def _resolve_principal(self) -> Optional[Principal]:
        token: AccessToken | None = get_access_token()

        if token is None:
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="principal_builder_error - no access token available",
                )
            )

        try:
            principal = self._principal_builder(token)
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Principal builder failed", exc_info=exc)
            raise McpError(
                ErrorData(
                    code=-32010,
                    message="Unauthorized",
                    data="principal_builder_error",
                )
            ) from exc

        if principal is not None and not isinstance(principal, Principal):
            raise TypeError(
                "principal_builder must return a cerbos.sdk.model.Principal"
            )
        return principal


def _python_to_protobuf_value(value: Any) -> struct_pb2.Value:
    """Recursively convert Python values to protobuf Value."""
    if value is None:
        return struct_pb2.Value(null_value=struct_pb2.NullValue.NULL_VALUE)
    elif isinstance(value, str):
        return struct_pb2.Value(string_value=value)
    elif isinstance(value, bool):
        return struct_pb2.Value(bool_value=value)
    elif isinstance(value, (int, float)):
        return struct_pb2.Value(number_value=float(value))
    elif isinstance(value, dict):
        struct_value = struct_pb2.Struct()
        for k, v in value.items():
            struct_value.fields[k].CopyFrom(_python_to_protobuf_value(v))
        return struct_pb2.Value(struct_value=struct_value)
    elif isinstance(value, (list, tuple)):
        list_value = struct_pb2.ListValue()
        for item in value:
            list_value.values.append(_python_to_protobuf_value(item))
        return struct_pb2.Value(list_value=list_value)
    else:
        # Fallback to string representation for other types
        return struct_pb2.Value(string_value=str(value))


def _principal_to_proto(principal: Principal) -> engine_pb2.Principal:
    # Convert attributes to struct_pb2.Value format recursively
    attr = {}
    for key, value in principal.attr.items():
        attr[key] = _python_to_protobuf_value(value)

    return engine_pb2.Principal(
        id=principal.id,
        policy_version=principal.policy_version,
        roles=principal.roles,
        attr=attr,
    )


def _resource_to_proto(resource: Resource) -> engine_pb2.Resource:
    # Convert attributes to struct_pb2.Value format recursively
    attr = {}
    for key, value in resource.attr.items():
        attr[key] = _python_to_protobuf_value(value)

    return engine_pb2.Resource(
        id=resource.id,
        kind=resource.kind,
        policy_version=resource.policy_version,
        attr=attr,
    )


def _env_tls(name: str, default: bool | str) -> bool | str:
    raw = os.getenv(name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return raw
