# cerbos-fastmcp

[FastMCP](https://gofastmcp.com/) middleware powered by
[Cerbos](https://cerbos.dev). Authorize every MCP tool call, prompt request,
and resource query against your Cerbos policies without rewriting your FastMCP
server.

## Why cerbos-fastmcp

- Use the Cerbos Policy Decision Point (PDP) you already trust.
- Apply fine-grained rules to tools, prompts, and resources.
- Bring your own principal builder (sync or async).
- Configure through environment variables for easy deployment.
- Ship with an example server and matching policies.

## Getting started

```bash
pip install cerbos-fastmcp
```

Prefer [`uv`](https://github.com/astral-sh/uv)?

```bash
uv pip install cerbos-fastmcp
```

> **Heads up**
> Install the [Cerbos](https://docs.cerbos.dev/cerbos/latest)
> CLI locally so you can run the PDP alongside your FastMCP server during
> development.

## Quick start

```python
from cerbos.sdk.model import Principal
from fastmcp import FastMCP
from fastmcp.server.dependencies import AccessToken

from cerbos_fastmcp import CerbosAuthorizationMiddleware


def build_principal(token: AccessToken) -> Principal | None:
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


app = FastMCP("My Cerbos-protected MCP", auth=my_auth)
app.add_middleware(
    CerbosAuthorizationMiddleware(
        principal_builder=build_principal,
        resource_kind="mcp_server",
    )
)
```

The middleware creates a Cerbos gRPC client using `CERBOS_HOST` during the FastMCP
`on_initialize` hook, verifying connectivity before any requests are handled. Provide an
`AsyncCerbosClient` instance if you want to manage connections yourself.

## Policy model

The middleware expects a Cerbos resource policy where the kind defaults to
`mcp_server`. Each FastMCP operation maps to an action string:

- `tools/list` gate the tool catalogue.
- `tools/list::<name>` decide if a tool is visible.
- `tools/call::<name>` authorize execution.
- `prompts/list` and `resources/list` cover the remaining MCP commands.

A complete sample lives in `policies/mcp_tool.yaml` and is reproduced in
[docs/policies.md](docs/policies.md). It also demonstrates schema usage and
regional constraints for data access.

## Configuration

Environment variables let you tweak behaviour without code changes:

| Variable               | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `CERBOS_HOST`          | Cerbos PDP gRPC endpoint (`host:port`).                |
| `CERBOS_RESOURCE_KIND` | Default resource kind (defaults to `mcp_server`).      |
| `CERBOS_TLS_VERIFY`    | `true`/`false` or a CA bundle path for TLS validation. |

## Example server

Run the bundled demo server and PDP in one command:

```bash
cerbos run -- uv run python -m cerbos_fastmcp.examples.server
```

The server listens on port 8000 and uses the policies in `policies/`. Import
`cerbos_fastmcp.examples.create_example_server()` in your own tests if you need a
pre-wired FastMCP instance.

## Testing

Install the dev dependencies and execute the test suite inside a Cerbos context:

```bash
uv pip install '.[dev]'
cerbos run -- uv run pytest
```

`cerbos run` launches a temporary PDP, sets `CERBOS_GRPC`/`CERBOS_HTTP`, and then
hands control back to `pytest`.

### Production guidance

**Local development** → Install Cerbos on your workstation (see the Getting
Started note) so you can run the PDP alongside FastMCP.

**Production** → Operate Cerbos as a managed service instance—ideally as a
sidecar next to your MCP server. The [Cerbos documentation](https://docs.cerbos.dev/)
covers deployment patterns, configuration, and operational best practices.

Bolt on [Cerbos Hub](http://cerbos.dev/hub) for production control plane needs:
policy distribution, CI integration, audit logs, and a collaborative policy IDE
for the teams managing access to your MCP server.

## Documentation

Extended guides live under [`docs/`](docs/index.md): installation, configuration,
policy design, testing strategy, and details about the example server.

## License

Apache 2.0 © Cerbos
