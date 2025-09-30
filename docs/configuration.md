# Configuration

## Middleware setup

Add the middleware to your [FastMCP](https://gofastmcp.com/) app:

```python
from fastmcp import FastMCP
from fastmcp_cerbos import CerbosAuthorizationMiddleware

app = FastMCP("My MCP", auth=my_auth)
app.add_middleware(
    CerbosAuthorizationMiddleware(
        principal_builder=build_principal,
        cerbos_host="localhost:3593",  # optional when CERBOS_HOST is set
        resource_kind="mcp_server",
        tls_verify=False,
    )
)
```

Key parameters:

- `principal_builder`: required. Turns an `AccessToken` into a
  `cerbos.sdk.model.Principal`. Async functions are supported.
- `cerbos_host`: optional when `CERBOS_HOST` is set. Accepts `host:port`.
- `cerbos_client`: inject an existing `AsyncCerbosClient` if you manage the
  lifecycle yourself.
- `resource_kind`: default `mcp_server`. Override per deployment if needed.
- `tls_verify`: `False`, `True`, or a path to a CA bundle.

## Environment variables

| Variable | Description |
| --- | --- |
| `CERBOS_HOST` | Cerbos PDP gRPC endpoint (`host:port`). |
| `CERBOS_RESOURCE_KIND` | Default resource kind used when checking policies. |
| `CERBOS_TLS_VERIFY` | `true`/`false` or path to a CA bundle. |

## Access tokens

The middleware obtains the FastMCP access token from
`fastmcp.server.dependencies.get_access_token()`. Ensure your authentication
provider populates the claims referenced by your Cerbos policies (for example
`sub`, `roles`, `department`, `region`). Returning `None` from the principal
builder results in a `McpError` with `data="missing_principal"`.
