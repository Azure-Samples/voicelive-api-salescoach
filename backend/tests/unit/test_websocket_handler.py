"""Tests for the websocket_handler module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

from src.services.websocket_handler import AZURE_VOICE_API_VERSION, VoiceProxyHandler


class TestVoiceProxyHandler:
    """Test cases for VoiceProxyHandler."""

    def test_voice_proxy_handler_initialization(self):
        """Test handler initialization."""
        agent_manager = Mock()

        handler = VoiceProxyHandler(agent_manager)

        assert handler.agent_manager == agent_manager

    @patch("src.services.websocket_handler.config")
    def test_build_endpoint(self, mock_config):
        """Test building the Azure endpoint URL."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_ai_resource_name": "test-resource",
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())
        endpoint = handler._build_endpoint()

        assert endpoint == "https://test-resource.cognitiveservices.azure.com"

    @patch("src.services.websocket_handler.config")
    def test_get_model_with_azure_agent(self, mock_config):
        """Test getting model name with Azure agent configuration."""
        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": True, "model": "gpt-4o"}

        model = handler._get_model(agent_config)

        assert model is None

    @patch("src.services.websocket_handler.config")
    def test_get_model_with_local_agent(self, mock_config):
        """Test getting model name with local agent configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": False, "model": "gpt-4"}

        model = handler._get_model(agent_config)

        assert model == "gpt-4"

    @patch("src.services.websocket_handler.config")
    def test_get_model_without_agent_config_with_global_agent_id(self, mock_config):
        """Test getting model name without agent config but with global agent_id."""
        mock_config.__getitem__.side_effect = lambda key: {
            "agent_id": "static-agent-123",
        }.get(key, "")

        handler = VoiceProxyHandler(Mock())
        model = handler._get_model(None)

        assert model is None

    @patch("src.services.websocket_handler.config")
    def test_get_model_without_agent_config(self, mock_config):
        """Test getting model name without agent config."""
        mock_config.__getitem__.side_effect = lambda key: {
            "agent_id": "",
            "model_deployment_name": "gpt-4o",
        }.get(key, "")

        handler = VoiceProxyHandler(Mock())
        model = handler._get_model(None)

        assert model == "gpt-4o"

    @patch("src.services.websocket_handler.config")
    def test_foundry_agent_connection_pins_version(self, mock_config):
        values = {
            "agent_id": "",
            "agent_name": "",
            "azure_ai_project_name": "",
            "project_endpoint": "https://test.services.ai.azure.com/api/projects/sales/",
        }
        mock_config.__getitem__.side_effect = lambda key: values.get(key, "")
        handler = VoiceProxyHandler(Mock())
        agent = {"is_azure_agent": True, "azure_agent_name": "sales-coach", "azure_agent_version": "2"}
        assert handler._get_model(agent) is None
        assert handler._build_query_params("sales-coach", agent) == {}
        assert handler._build_agent_connection_params(agent) == {
            "agent_name": "sales-coach",
            "agent_version": "2",
            "project_name": "sales",
        }

    @patch("src.services.websocket_handler.config")
    def test_configured_foundry_agent_connection(self, mock_config):
        values = {"agent_name": "existing-coach", "agent_version": "", "azure_ai_project_name": "sales"}
        mock_config.__getitem__.side_effect = lambda key: values.get(key, "")
        handler = VoiceProxyHandler(Mock())
        assert handler._get_model(None) is None
        assert handler._build_query_params(None, None) == {}
        assert handler._build_agent_connection_params(None) == {"agent_name": "existing-coach", "project_name": "sales"}

    @patch("src.services.websocket_handler.config")
    def test_foundry_agent_requires_project(self, mock_config):
        mock_config.__getitem__.return_value = ""
        with pytest.raises(ValueError, match="requires AZURE_AI_PROJECT_NAME"):
            VoiceProxyHandler(Mock())._build_agent_connection_params({"azure_agent_name": "sales-coach"})

    @patch("src.services.websocket_handler.config")
    def test_build_query_params_with_azure_agent(self, mock_config):
        """Test building query params with Azure agent configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_ai_project_name": "test-project",
        }.get(key, "")

        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": True}

        params = handler._build_query_params("agent-123", agent_config)

        assert params["agent-id"] == "agent-123"
        assert params["agent-project-name"] == "test-project"

    @patch("src.services.websocket_handler.config")
    def test_build_query_params_with_local_agent(self, mock_config):
        """Test building query params with local agent configuration."""
        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": False}

        params = handler._build_query_params("local-agent-123", agent_config)

        assert params == {}

    @patch("src.services.websocket_handler.config")
    def test_build_query_params_without_agent_config_with_global_agent_id(self, mock_config):
        """Test building query params without agent config but with global agent_id."""
        mock_config.__getitem__.side_effect = lambda key: {
            "agent_id": "static-agent-123",
        }.get(key, "")

        handler = VoiceProxyHandler(Mock())
        params = handler._build_query_params(None, None)

        assert params["agent-id"] == "static-agent-123"

    @patch("src.services.websocket_handler.config")
    def test_build_session_config_without_agent(self, mock_config):
        """Test building session config without agent configuration."""
        mock_config.get.side_effect = lambda key, default=None: {
            "azure_voice_name": "en-US-TestVoice",
            "azure_voice_type": "azure-standard",
            "azure_avatar_character": "lisa",
            "azure_avatar_style": "casual-sitting",
        }.get(key, default)

        handler = VoiceProxyHandler(Mock())
        session = handler._build_session_config(None)

        assert "modalities" in session
        assert "turn_detection" in session
        assert "voice" in session

    @patch("src.services.websocket_handler.config")
    def test_build_session_config_with_local_agent(self, mock_config):
        """Test building session config with local agent configuration."""
        mock_config.get.side_effect = lambda key, default=None: {
            "azure_voice_name": "en-US-TestVoice",
            "azure_voice_type": "azure-standard",
            "azure_avatar_character": "lisa",
            "azure_avatar_style": "casual-sitting",
        }.get(key, default)

        handler = VoiceProxyHandler(Mock())
        agent_config = {
            "is_azure_agent": False,
            "instructions": "Test instructions",
            "temperature": 0.8,
            "max_tokens": 1000,
        }

        session = handler._build_session_config(agent_config)

        assert session["instructions"] == "Test instructions"
        assert session["temperature"] == 0.8
        assert session["max_response_output_tokens"] == 1000

    @pytest.mark.parametrize("is_photo", [False, True])
    def test_avatar_configuration_uses_ga_wire_fields(self, is_photo):
        avatar = VoiceProxyHandler(Mock())._build_avatar_config("lisa", "casual-sitting", is_photo).as_dict()
        assert avatar["type"] == ("photo-avatar" if is_photo else "video-avatar")
        assert avatar["character"] == "lisa"
        assert avatar["output_protocol"] == "webrtc"
        assert avatar["customized"] is False
        if is_photo:
            assert avatar["model"] == "vasa-1"
            assert "style" not in avatar
        else:
            assert avatar["style"] == "casual-sitting"

    @patch("src.services.websocket_handler.config")
    def test_foundry_agent_uses_entra_even_when_api_key_is_configured(self, mock_config):
        mock_config.get.return_value = "test-api-key"
        credential = VoiceProxyHandler(Mock())._get_credential(use_agent=True)
        assert isinstance(credential, AsyncDefaultAzureCredential)

    def test_empty_avatar_style_is_omitted_instead_of_cleared(self):
        avatar = VoiceProxyHandler(Mock())._build_avatar_config("lisa", "", False).as_dict()
        assert "style" not in avatar

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending a message to WebSocket."""
        handler = VoiceProxyHandler(Mock())

        mock_ws = Mock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            message = {"type": "test", "data": "test data"}
            await handler._send_message(mock_ws, message)

            mock_loop.return_value.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error(self):
        """Test sending an error message to WebSocket."""
        handler = VoiceProxyHandler(Mock())

        mock_ws = Mock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await handler._send_error(mock_ws, "Test error")

            mock_loop.return_value.run_in_executor.assert_called_once()

    @patch("src.services.websocket_handler.config")
    def test_get_credential_success(self, mock_config):
        """Test getting credential with valid API key."""
        mock_config.get.return_value = "test-api-key"

        handler = VoiceProxyHandler(Mock())
        credential = handler._get_credential()

        assert credential is not None
        assert credential.key == "test-api-key"

    @patch("src.services.websocket_handler.config")
    def test_get_credential_missing_key_falls_back_to_managed_identity(self, mock_config):
        """Test getting credential falls back to DefaultAzureCredential when no API key."""
        mock_config.get.return_value = None

        handler = VoiceProxyHandler(Mock())
        credential = handler._get_credential()

        assert isinstance(credential, AsyncDefaultAzureCredential)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("use_api_key", [False, True])
    @pytest.mark.parametrize("connection_error", [None, RuntimeError("Connection failed"), asyncio.CancelledError()])
    async def test_handle_connection_closes_managed_identity(self, use_api_key, connection_error):
        """Close managed identity credentials on disconnect, failure, and cancellation."""
        credential = AzureKeyCredential("test-key") if use_api_key else AsyncMock(spec=AsyncDefaultAzureCredential)
        handler = VoiceProxyHandler(Mock())
        send_error = AsyncMock()

        with (
            patch.multiple(
                handler,
                _get_agent_id_from_client=AsyncMock(return_value=None),
                _get_credential=Mock(return_value=credential),
                _send_initial_config=AsyncMock(),
                _handle_message_forwarding=AsyncMock(),
                _send_message=AsyncMock(),
                _send_error=send_error,
            ),
            patch("src.services.websocket_handler.connect") as mock_connect,
        ):
            mock_connect.return_value.__aenter__.side_effect = connection_error
            if isinstance(connection_error, asyncio.CancelledError):
                with pytest.raises(asyncio.CancelledError):
                    await handler.handle_connection(Mock())
            else:
                await handler.handle_connection(Mock())
                if connection_error:
                    send_error.assert_awaited_once()
                else:
                    send_error.assert_not_awaited()
                    assert mock_connect.call_args.kwargs["api_version"] == AZURE_VOICE_API_VERSION == "2026-07-15"

        if not use_api_key:
            credential.close.assert_awaited_once()
