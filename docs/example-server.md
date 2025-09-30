# Example server

`fastmcp_cerbos.examples.server` is a ready-to-run
[FastMCP](https://gofastmcp.com/) instance protected by Cerbos. It exposes a
handful of demo tools (sales, engineering, HR, admin) and a principal builder
that maps JWT claims to Cerbos principals.

## Run locally

```bash
cerbos run -- uv run python -m fastmcp_cerbos.examples.server
```

The command launches a Cerbos PDP with the repository policies, sets the
`CERBOS_GRPC`/`CERBOS_HTTP` environment variables, and starts the MCP server on
port 8000.

Use the static tokens defined in the module (`ian`, `sally`, `harry`) to exercise
the policy rules.

## Reuse in tests

Import the helper to get a configured server:

```python
from fastmcp_cerbos.examples import create_example_server

app = create_example_server()
```

You can then mount additional tools, swap the principal builder, or plug the app
into your own integration harness.
