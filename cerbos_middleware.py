"""Cerbos authorization middleware for FastMCP."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from typing import Any, Awaitable, Callable, Optional

from cerbos.engine.v1 import engine_pb2
from cerbos.sdk.grpc.client import AsyncCerbosClient
from cerbos.sdk.model import Principal, Resource
from fastmcp.exceptions import McpError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from google.protobuf.json_format import ParseDict
from mcp.types import CallToolRequestParams, ErrorData
from fastmcp.server.dependencies import get_access_token, AccessToken


logger = logging.getLogger(__name__)

PrincipalBuilder = Callable[
    [AccessToken],
    Awaitable[Optional[Principal]] | Optional[Principal],
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
        if cerbos_client is None and not self._cerbos_host:
            raise ValueError(
                "cerbos_host must be provided or CERBOS_HOST environment variable must be set"
            )

        self._resource_kind = resource_kind or os.getenv(
            "CERBOS_RESOURCE_KIND", "mcp_tool"
        )

        self._tls_verify = (
            tls_verify
            if tls_verify is not None
            else _env_tls("CERBOS_TLS_VERIFY", False)
        )

        self._client: Optional[AsyncCerbosClient] = cerbos_client
        self._owns_client = cerbos_client is None
        self._client_lock = asyncio.Lock()

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next,
    ) -> Any:
        principal = await self._resolve_principal(context)
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

        action = f"call::{tool_name}"
        resource = Resource(id=tool_name, kind=self._resource_kind)
        resource.attr.update(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "source": context.source,
            }
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
                ErrorData(code=-32010, message="Unauthorized", data="cerbos_denied")
            )

        logger.debug(
            "Cerbos authorized tool call",
            extra={"principal": principal.id, "action": action},
        )
        return await call_next(context)

    async def on_list_tools(self, context, call_next):
        original_result = await super().on_list_tools(context, call_next)
        principal = await self._resolve_principal(context)
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
            action = f"list::{tool.name}"
            resource = Resource(id=tool.name, kind=self._resource_kind)
            resource.attr.update(
                {
                    "tool_name": tool.name,
                    "arguments": {},
                    "source": context.source,
                }
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
    

    async def _is_allowed(
        self, action: str, principal: Principal, resource: Resource
    ) -> bool:
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
            raise RuntimeError("Cerbos client was provided but is not available")

        async with self._client_lock:
            if self._client is None:
                if not self._cerbos_host:
                    raise RuntimeError("Cerbos host is not configured")
                self._client = AsyncCerbosClient(
                    self._cerbos_host,
                    tls_verify=self._tls_verify,
                )
            return self._client

    async def _resolve_principal(
        self, context: MiddlewareContext[CallToolRequestParams]
    ) -> Optional[Principal]:
        
        token: AccessToken | None = get_access_token()

        # dump token for debugging
        logger.debug(f"Access token: {token}")
        

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
                "principal_builder must return a cerbos.sdk.model.Principal or None"
            )
        return principal


def _principal_to_proto(principal: Principal) -> engine_pb2.Principal:
    proto = engine_pb2.Principal()
    ParseDict(principal.to_dict(), proto)
    return proto


def _resource_to_proto(resource: Resource) -> engine_pb2.Resource:
    proto = engine_pb2.Resource()
    ParseDict(resource.to_dict(), proto)
    return proto


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


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
