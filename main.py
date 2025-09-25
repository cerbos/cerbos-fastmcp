from typing import Optional
from fastmcp import FastMCP
from mcp import ErrorData, McpError

from cerbos_middleware import CerbosAuthorizationMiddleware
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from cerbos.sdk.model import Principal
from fastmcp.server.dependencies import AccessToken

verifier = StaticTokenVerifier(
    tokens={
        "ian": {
            "client_id": "ian",
            "sub": "ian",
            "scopes": ["read:data", "write:data", "admin:users"],
            "roles": ["admin"],
            "department": "engineering",
            "region": "us",
        },
        "sally": {
            "client_id": "sally",
            "sub": "sally",
            "scopes": ["read:data"],
            "roles": ["sales"],
            "department": "sales",
            "region": "emea",
        }
    }
)


mcp = FastMCP("Cerbos + FastMCP Example", auth=verifier)

def principal_builder(token: AccessToken) -> Principal:
    user_id = token.claims.get("sub", "") if token else None
    if user_id is None:
        raise McpError(
            ErrorData(
                code=-32010,
                message="Unauthorized",
                data="principal_builder_error - no sub claim available",
            )
        )

    return Principal(
        id=user_id,
        roles=token.claims.get("roles", []),
        attr={
            "department": token.claims.get("department", ""),
            "region": token.claims.get("region", ""),
        }
    )

mcp.add_middleware(CerbosAuthorizationMiddleware(
    cerbos_host="localhost:3593",
    principal_builder=principal_builder,
))


@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

@mcp.tool
def goodbye(name: str) -> str:
    return f"Goodbye, {name}!"


if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
