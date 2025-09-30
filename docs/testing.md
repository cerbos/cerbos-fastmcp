# Testing

The repository ships with two layers of tests:

- Unit tests using a stubbed Cerbos client.
- Integration tests that talk to a live Cerbos PDP.

## Run the suite

```bash
uv pip install '.[dev]'
cerbos run -- uv run pytest
```

`cerbos run` loads the `policies/` directory, starts the PDP, exports
`CERBOS_GRPC`, and executes `pytest` inside that context.

## Continuous integration

`.github/workflows/ci.yaml` mirrors the local workflow: install dependencies,
then run `cerbos run -- uv run pytest` on every push and pull request.

## Writing new tests

- Monkeypatch `fastmcp_cerbos.middleware.get_access_token` so the middleware sees
your mocked `AccessToken` objects.
- Reuse the fixtures in `tests/test_integration.py` to generate principals with
custom roles or regions.
- Scope async Cerbos clients to a single test. Mixing event loops will trigger
runtime errors from `grpc.aio`.
