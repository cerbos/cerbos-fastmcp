# Installation

fastmcp-cerbos targets Python 3.11+. Install it alongside your
[FastMCP](https://gofastmcp.com/) server:

```bash
pip install fastmcp-cerbos
```

or, with [`uv`](https://github.com/astral-sh/uv):

```bash
uv pip install fastmcp-cerbos
```

The package pulls in the Cerbos Python SDK and FastMCP as dependencies. Make
sure a Cerbos PDP (self-hosted or managed) is reachable over gRPC when the
middleware runs.

For local workflows you will also need the Cerbos CLI so you can launch a PDP
next to your FastMCP server. Follow the installation guide in the
[Cerbos documentation](https://docs.cerbos.dev).
