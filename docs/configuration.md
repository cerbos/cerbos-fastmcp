# Configuration

## Middleware setup

Add the middleware to your [FastMCP](https://gofastmcp.com/) app:

```python
from fastmcp import FastMCP
from cerbos_fastmcp import CerbosAuthorizationMiddleware

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

- `principal_builder`: **Required**. Turns an `AccessToken` into a
  `cerbos.sdk.model.Principal`. Both sync and async functions are supported.
- `cerbos_host`: Optional when `CERBOS_HOST` is set. Accepts `host:port` format.
  The middleware will immediately create and validate the Cerbos client connection
  during initialization to provide fail-fast behavior.
- `cerbos_client`: Optional. Inject an existing `AsyncCerbosClient` if you manage the
  lifecycle yourself. When provided, `cerbos_host` is ignored.
- `resource_kind`: Optional, default `mcp_server`. Override per deployment if needed.
  Can also be set via `CERBOS_RESOURCE_KIND` environment variable.
- `tls_verify`: Optional, default `False`. Can be `False`, `True`, or a path to a CA bundle.
  Can also be set via `CERBOS_TLS_VERIFY` environment variable.

## Environment variables

| Variable               | Description                                        |
| ---------------------- | -------------------------------------------------- |
| `CERBOS_HOST`          | Cerbos PDP gRPC endpoint (`host:port`).            |
| `CERBOS_RESOURCE_KIND` | Default resource kind used when checking policies. |
| `CERBOS_TLS_VERIFY`    | `true`/`false` or path to a CA bundle.             |

### TLS verification values

The `CERBOS_TLS_VERIFY` environment variable supports multiple formats:

- **Truthy values** (`true`, `True`, `TRUE`, `1`, `yes`, `on`): Enable TLS verification
- **Falsy values** (`false`, `False`, `FALSE`, `0`, `no`, `off`): Disable TLS verification
- **File path**: Path to a custom CA certificate bundle

## Fail-fast behavior

The middleware **immediately validates** Cerbos connectivity during initialization when:

- `cerbos_host` is provided (either as parameter or `CERBOS_HOST` env var)
- No explicit `cerbos_client` is passed

This ensures configuration errors (invalid hostnames, TLS issues, unreachable servers) are caught at startup rather than during the first request, making debugging much easier.

If you need to defer connection establishment, pass a pre-configured `AsyncCerbosClient` via the `cerbos_client` parameter.

## Access tokens

The middleware obtains the FastMCP access token from
`fastmcp.server.dependencies.get_access_token()`. Ensure your authentication
provider populates the claims referenced by your Cerbos policies (for example
`sub`, `roles`, `department`, `region`). Returning `None` from the principal
builder results in a `McpError` with `data="missing_principal"`.
