# Testing

The repository ships with three layers of tests:

- **Unit tests** (`test_middleware.py`) using a stubbed Cerbos client for authorization logic.
- **Client configuration tests** (`test_client_config.py`) for middleware setup, environment variables, and fail-fast behavior.
- **Integration tests** (`test_integration.py`) that talk to a live Cerbos PDP.

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

### Authorization logic tests

- Monkeypatch `cerbos_fastmcp.middleware.get_access_token` so the middleware sees
  your mocked `AccessToken` objects.
- Reuse the fixtures in `tests/test_integration.py` to generate principals with
  custom roles or regions.
- Use the `DummyClient` class from `test_middleware.py` for predictable authorization responses.

### Configuration tests

- Mock `AsyncCerbosClient` creation to test parameter handling without real network calls.
- Use `monkeypatch.setenv()` to test environment variable behavior.
- Test fail-fast scenarios by making mocked client construction raise exceptions.

### Integration tests

- Scope async Cerbos clients to a single test. Mixing event loops will trigger
  runtime errors from `grpc.aio`.
- Use the live Cerbos PDP started by `cerbos run` for realistic policy evaluation.
