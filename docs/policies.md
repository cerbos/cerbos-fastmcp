# Policy design

fastmcp-cerbos maps [FastMCP](https://gofastmcp.com/) operations to Cerbos resource actions. The default
resource kind is `mcp_server` (override it with `resource_kind` or
`CERBOS_RESOURCE_KIND`).

| FastMCP operation | Cerbos action |
| --- | --- |
| List tools | `tools/list` |
| Tool visible in list | `tools/list::<tool_name>` |
| Call tool | `tools/call::<tool_name>` |
| List prompts | `prompts/list` |
| List resources | `resources/list` |

A working policy ships in `policies/mcp_tool.yaml`:

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

The policy references schemas in `policies/_schemas/` and demonstrates how to
constrain tool usage by region. Adapt the roles, attributes, and actions to match
your own MCP deployment.

### Tips

- Keep resource attributes small. The middleware passes tool arguments and
  metadata to Cerbos as protobuf `struct` values.
- Use Cerbos derived roles or variables if you need reusable logic.
- Apply audit logging in Cerbos to track denied MCP actions.
