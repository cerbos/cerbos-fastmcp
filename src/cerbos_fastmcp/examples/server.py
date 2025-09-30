"""Example FastMCP server protected by Cerbos middleware."""

from __future__ import annotations

from typing import Optional

from cerbos.sdk.model import Principal
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import AccessToken
from mcp import ErrorData, McpError

from cerbos_fastmcp import CerbosAuthorizationMiddleware


def _build_static_verifier() -> StaticTokenVerifier:
    return StaticTokenVerifier(
        tokens={
            "ian": {
                "client_id": "ian",
                "sub": "ian",
                "scopes": ["mcp:connect"],
                "roles": ["ADMIN"],
                "department": "engineering",
                "region": "NA",
            },
            "sally": {
                "client_id": "sally",
                "sub": "sally",
                "scopes": ["mcp:connect"],
                "roles": ["SALES"],
                "department": "SALES",
                "region": "EMEA",
            },
            "harry": {
                "client_id": "harry",
                "sub": "harry",
                "scopes": ["mcp:connect"],
                "roles": ["HR"],
                "department": "HR",
                "region": "APAC",
            },
        },
        required_scopes=["mcp:connect"],
    )


def _principal_builder(token: AccessToken) -> Principal:
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
        },
    )


def create_example_server() -> FastMCP:
    """Build the example Cerbos-protected FastMCP server."""

    mcp = FastMCP("Cerbos + FastMCP Example", auth=_build_static_verifier())
    mcp.add_middleware(
        CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            resource_kind="mcp_server",
        )
    )

    @mcp.tool(description="Greet a person")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    @mcp.tool(description="Retrieve sales data")
    def get_sales_data(region: str) -> str:
        return f"This is the sales data for {region}!"

    @mcp.tool(description="Retrieve engineering data")
    def get_engineering_data(region: str) -> str:
        return f"This is the engineering data for {region}!"

    @mcp.tool(description="Retrieve HR records")
    def get_hr_records(department: Optional[str] = None) -> str:
        if department:
            return f"This is the HR records for the {department} department!"
        return "This is the HR records for all departments!"

    @mcp.tool(description="Admin only tool")
    def admin_tool() -> str:
        return "This is an admin only tool!"

    @mcp.prompt
    def sampleprompt() -> str:
        return "Sample prompt response."

    @mcp.resource("prompt://sample")
    def data_resource() -> dict:
        return {"id": "resource_id", "type": "data", "sensitivity": "high"}

    return mcp


def main() -> None:
    server = create_example_server()
    server.run(transport="http", port=8000)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
