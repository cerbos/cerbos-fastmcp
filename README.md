# fastmcp-cerbos

`fastmcp-cerbos` provides a reusable Cerbos authorization middleware for
[FastMCP](https://gofastmcp.com/) servers. It wires the
[cerbos Python SDK](https://github.com/cerbos/cerbos-sdk-python) into the
FastMCP middleware pipeline, so every MCP tool call, resource listing, or prompt
retrieval is authorized by your Cerbos policies before being executed.

## Features

- ✅ Works with the official Cerbos Python SDK (`AsyncCerbosClient`)
- ✅ Checks `tools.call`, `tools.list`, `prompts.list`, and `resources.list`
- ✅ Lets you provide a synchronous or async principal builder
- ✅ Respects `CERBOS_HOST`, `CERBOS_RESOURCE_KIND`, and `CERBOS_TLS_VERIFY`
  environment variables for zero-code configuration tweaks

## Installation

```bash
pip install fastmcp-cerbos
```

## Quick start

```python
from cerbos.sdk.model import Principal
from fastmcp_cerbos import CerbosAuthorizationMiddleware
from fastmcp.server.dependencies import AccessToken


async def build_principal(token: AccessToken) -> Principal | None:
    # Translate the access token into a Cerbos principal definition
    if token is None:
        return None

    return Principal(
        id=token.claims["sub"],
        roles=token.claims.get("roles", []),
        attr={
            "department": token.claims.get("department", ""),
            "region": token.claims.get("region", ""),
        },
    )


def create_middleware() -> CerbosAuthorizationMiddleware:
    return CerbosAuthorizationMiddleware(
        cerbos_host="localhost:3593",
        principal_builder=build_principal,
        resource_kind="mcp_server",
        tls_verify=False,  # or a CA bundle path/True if you use TLS
    )
```

Register the middleware with your FastMCP application:

```python
from fastmcp import FastMCP

mcp = FastMCP("My Cerbos-protected MCP", auth=...)  # configure your auth provider
mcp.add_middleware(create_middleware())
```

## Cerbos policy requirements

The middleware expects a Cerbos resource policy for the `mcp_server` resource
kind (or the alternative kind you pass to the middleware). Actions follow the
pattern Cerbos uses for resource policies:

- `tools/list` gates the full tool listing
- `tools/list::<tool-name>` determines whether an individual tool appears in the
  list response
- `tools/call::<tool-name>` determines whether the tool can be invoked
- `resources/list` and `prompts/list` cover the corresponding MCP commands

Below is the demo policy shipped in `policies/mcp_tool.yaml` which you can adapt
for your own deployment:

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  resource: mcp_server
  version: default
  rules:
    - actions:
        - resources/list
        - prompts/list
        - tools/list
        - tools/list::greet
        - tools/call::greet
        - tools/list::admin_tool
        - tools/call::admin_tool
        - tools/list::get_sales_data
        - tools/call::get_sales_data
        - tools/list::get_engineering_data
        - tools/call::get_engineering_data
      roles: [ADMIN]
      effect: EFFECT_ALLOW
    - actions:
        - prompts/list
        - tools/list
        - tools/list::greet
        - tools/call::greet
        - tools/list::get_sales_data
      roles: [SALES]
      effect: EFFECT_ALLOW
    - actions:
        - tools/list
        - tools/list::greet
        - tools/call::greet
        - tools/list::get_hr_records
        - tools/call::get_hr_records
      roles: [HR]
      effect: EFFECT_ALLOW
    - actions: [tools/call::get_sales_data]
      roles: [SALES]
      effect: EFFECT_ALLOW
      condition:
        match:
          expr: R.attr.arguments.region == P.attr.region
```

Make sure your principal builder populates the role names used in the policy and
any attributes referenced by policy conditions.

## Environment variables

The middleware can be configured without code changes using the following
environment variables:

- `CERBOS_HOST`: Cerbos PDP endpoint (e.g. `localhost:3593` for gRPC)
- `CERBOS_RESOURCE_KIND`: Default Cerbos resource kind (`mcp_server` by default)
- `CERBOS_TLS_VERIFY`: `true`/`false` or a path to a CA bundle for TLS validation

## Example server

The package ships with `fastmcp_cerbos.examples.server`, which spins up a demo
server protected by Cerbos. Launch it alongside a running Cerbos PDP instance
to see the middleware in action:

```bash
cerbos run -- uv run python -m fastmcp_cerbos.examples.server
```

Tests and integration harnesses can reuse the same logic via
`fastmcp_cerbos.examples.create_example_server()`. Review the `policies/`
directory for example Cerbos policies you can load with `start-cerbos.sh`.

## Testing

Run the test suite inside a Cerbos PDP context so the integration tests can talk
to a live Cerbos instance:

```bash
uv pip install '.[dev]'
cerbos run -- uv run pytest
```

The `cerbos run` wrapper starts a temporary PDP using the policies in
`./policies/` and exposes the gRPC endpoint through the `CERBOS_GRPC`
environment variable consumed by the tests.
