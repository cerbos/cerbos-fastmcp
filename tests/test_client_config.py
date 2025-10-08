"""Tests for Cerbos client configuration and failure scenarios."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from cerbos.sdk.grpc.client import AsyncCerbosClient
from cerbos.sdk.model import Principal
from fastmcp.server.dependencies import AccessToken
from fastmcp.server.middleware import MiddlewareContext

from cerbos_fastmcp import CerbosAuthorizationMiddleware


async def _principal_builder(token: AccessToken) -> Principal:
    return Principal(
        id=token.claims["sub"],
        roles=token.claims.get("roles", []),
        attr={
            "department": token.claims.get("department", ""),
            "region": token.claims.get("region", ""),
        },
    )


class TestClientConfiguration:
    """Test cases for client configuration scenarios."""

    def test_explicit_client_provided(self) -> None:
        """Test that explicitly provided client is used and not owned."""
        mock_client = Mock(spec=AsyncCerbosClient)

        middleware = CerbosAuthorizationMiddleware(
            principal_builder=_principal_builder,
            cerbos_client=mock_client,
        )

        assert middleware._client is mock_client
        assert not middleware._owns_client

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_client_created_from_host_parameter(
        self, mock_client_class: Mock
    ) -> None:
        """Test that client is created from cerbos_host parameter."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify=True,
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=True)
        assert middleware._client is mock_client_instance
        assert client is mock_client_instance
        assert middleware._owns_client

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_client_created_from_env_var(
        self, mock_client_class: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that client is created from CERBOS_HOST environment variable."""
        monkeypatch.setenv("CERBOS_HOST", "env-host:3593")
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            principal_builder=_principal_builder,
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with(
            "env-host:3593",
            tls_verify=False,  # default value
        )
        assert middleware._client is mock_client_instance
        assert client is mock_client_instance
        assert middleware._owns_client

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_host_parameter_overrides_env_var(
        self, mock_client_class: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cerbos_host parameter takes precedence over environment variable."""
        monkeypatch.setenv("CERBOS_HOST", "env-host:3593")
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="param-host:3593",
            principal_builder=_principal_builder,
        )

        await middleware._ensure_client()

        mock_client_class.assert_called_once_with("param-host:3593", tls_verify=False)

    def test_missing_host_and_client_raises_error(self) -> None:
        """Test that missing both cerbos_host and cerbos_client raises ValueError."""
        with pytest.raises(
            ValueError,
            match="cerbos_host must be provided or CERBOS_HOST environment variable must be set",
        ):
            CerbosAuthorizationMiddleware(
                principal_builder=_principal_builder,
            )

    def test_missing_principal_builder_raises_error(self) -> None:
        """Test that missing principal_builder raises ValueError."""
        with pytest.raises(ValueError, match="principal_builder must be provided"):
            CerbosAuthorizationMiddleware(
                cerbos_host="localhost:3593",
                principal_builder=None,  # type: ignore
            )


class TestTLSConfiguration:
    """Test cases for TLS configuration scenarios."""

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_verify_parameter_true(
        self, mock_client_class: Mock
    ) -> None:
        """Test TLS verification enabled via parameter."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify=True,
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=True)
        assert client is mock_client_instance

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_verify_parameter_false(
        self, mock_client_class: Mock
    ) -> None:
        """Test TLS verification disabled via parameter."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify=False,
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=False)
        assert client is mock_client_instance

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_verify_parameter_string(
        self, mock_client_class: Mock
    ) -> None:
        """Test TLS verification with custom certificate path."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify="/path/to/cert.pem",
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with(
            "localhost:3593", tls_verify="/path/to/cert.pem"
        )
        assert client is mock_client_instance

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("/path/to/cert.pem", "/path/to/cert.pem"),
        ],
    )
    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_verify_env_var(
        self,
        mock_client_class: Mock,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
        expected: bool | str,
    ) -> None:
        """Test TLS verification configuration from environment variable."""
        monkeypatch.setenv("CERBOS_TLS_VERIFY", env_value)
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=expected)
        assert client is mock_client_instance

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_parameter_overrides_env_var(
        self, mock_client_class: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that tls_verify parameter takes precedence over environment variable."""
        monkeypatch.setenv("CERBOS_TLS_VERIFY", "true")
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify=False,  # This should override the env var
        )

        client = await middleware._ensure_client()

        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=False)
        assert client is mock_client_instance


class TestResourceKindConfiguration:
    """Test cases for resource kind configuration scenarios."""

    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    def test_default_resource_kind(self, mock_client_class: Mock) -> None:
        """Test default resource kind is used when not specified."""
        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
        )

        assert middleware._resource_kind == "mcp_server"

    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    def test_custom_resource_kind_parameter(self, mock_client_class: Mock) -> None:
        """Test custom resource kind via parameter."""
        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            resource_kind="custom_server",
        )

        assert middleware._resource_kind == "custom_server"

    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    def test_resource_kind_env_var(
        self, mock_client_class: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test resource kind configuration from environment variable."""
        monkeypatch.setenv("CERBOS_RESOURCE_KIND", "env_server")

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
        )

        assert middleware._resource_kind == "env_server"

    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    def test_resource_kind_parameter_overrides_env_var(
        self, mock_client_class: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that resource_kind parameter takes precedence over environment variable."""
        monkeypatch.setenv("CERBOS_RESOURCE_KIND", "env_server")

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            resource_kind="param_server",
        )

        assert middleware._resource_kind == "param_server"


class TestClientLifecycle:
    """Test cases for client lifecycle management."""

    @pytest.mark.asyncio
    async def test_owned_client_cleanup(self) -> None:
        """Test that owned client is properly cleaned up."""
        mock_client = AsyncMock(spec=AsyncCerbosClient)

        with patch(
            "cerbos_fastmcp.middleware.AsyncCerbosClient", return_value=mock_client
        ):
            middleware = CerbosAuthorizationMiddleware(
                cerbos_host="localhost:3593",
                principal_builder=_principal_builder,
            )

            # Should own the client
            assert middleware._owns_client
            assert middleware._client is None

            client = await middleware._ensure_client()
            assert middleware._client is mock_client
            assert client is mock_client

            # Close should call client.close() and clear the reference
            await middleware.close()
            assert mock_client.close.await_count == 1
            assert middleware._client is None

    @pytest.mark.asyncio
    async def test_external_client_not_cleaned_up(self) -> None:
        """Test that external client is not cleaned up."""
        mock_client = Mock(spec=AsyncCerbosClient)

        middleware = CerbosAuthorizationMiddleware(
            principal_builder=_principal_builder,
            cerbos_client=mock_client,
        )

        # Should not own the client
        assert not middleware._owns_client
        assert middleware._client is mock_client

        # Close should not call client.close() or clear the reference
        await middleware.close()
        mock_client.close.assert_not_called()
        assert middleware._client is mock_client


class TestClientInitialization:
    """Test cases for client creation and initialization."""

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_client_creation_failure_during_initialization(
        self, mock_client_class: Mock
    ) -> None:
        """Test that client creation failures surface during initialization."""
        mock_client_class.side_effect = ConnectionError(
            "Cannot connect to Cerbos server"
        )

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="invalid-host:3593",
            principal_builder=_principal_builder,
        )

        with pytest.raises(ConnectionError, match="Cannot connect to Cerbos server"):
            await middleware._ensure_client()

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_tls_configuration_error_during_initialization(
        self, mock_client_class: Mock
    ) -> None:
        """Test that TLS configuration errors surface during initialization."""
        mock_client_class.side_effect = ValueError("Invalid TLS configuration")

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
            tls_verify="/invalid/path/cert.pem",
        )

        with pytest.raises(ValueError, match="Invalid TLS configuration"):
            await middleware._ensure_client()

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_client_cached_after_ensure_client(
        self, mock_client_class: Mock
    ) -> None:
        """Test that the client instance is cached after creation."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
        )

        first_client = await middleware._ensure_client()
        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=False)
        assert first_client is mock_client_instance
        assert mock_client_instance.server_info.await_count == 0

        second_client = await middleware._ensure_client()
        assert second_client is mock_client_instance
        assert mock_client_class.call_count == 1

    @pytest.mark.asyncio
    @patch("cerbos_fastmcp.middleware.AsyncCerbosClient")
    async def test_on_initialize_creates_client(
        self, mock_client_class: Mock
    ) -> None:
        """Test that the middleware initializes the client during startup."""
        mock_client_instance = AsyncMock(spec=AsyncCerbosClient)
        mock_client_class.return_value = mock_client_instance

        middleware = CerbosAuthorizationMiddleware(
            cerbos_host="localhost:3593",
            principal_builder=_principal_builder,
        )

        context = MiddlewareContext(
            message=None,
            method="initialize",
        )
        call_next = AsyncMock()

        await middleware.on_initialize(context, call_next)

        call_next.assert_awaited_once_with(context)
        mock_client_class.assert_called_once_with("localhost:3593", tls_verify=False)
        assert mock_client_instance.server_info.await_count == 1
