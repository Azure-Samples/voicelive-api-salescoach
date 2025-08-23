"""Tests for the websocket_handler module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from websocket_handler import VoiceProxyHandler


class TestVoiceProxyHandler:
    """Test cases for VoiceProxyHandler."""

    def test_voice_proxy_handler_initialization(self):
        """Test handler initialization."""
        agent_manager = Mock()

        handler = VoiceProxyHandler(agent_manager)

        assert handler.agent_manager == agent_manager

    @patch("websocket_handler.config")
    def test_build_azure_url_with_azure_agent(self, mock_config):
        """Test building Azure URL with Azure agent configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_ai_resource_name": "test-resource",
            "azure_ai_project_name": "test-project",
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": True, "model": "gpt-4o"}

        url = handler._build_azure_url("agent-123", agent_config)

        assert "agent-id=agent-123" in url
        assert "test-resource" in url
        assert "test-project" in url

    @patch("websocket_handler.config")
    def test_build_azure_url_with_local_agent(self, mock_config):
        """Test building Azure URL with local agent configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_ai_resource_name": "test-resource",
            "azure_ai_project_name": "test-project",
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())
        agent_config = {"is_azure_agent": False, "model": "gpt-4"}

        url = handler._build_azure_url("local-agent-123", agent_config)

        assert "model=gpt-4" in url
        assert "agent-id=" not in url or "agent-id=&" in url
        assert "test-resource" in url

    @patch("websocket_handler.config")
    def test_build_azure_url_without_agent_config(self, mock_config):
        """Test building Azure URL without agent configuration."""
        mock_config.__getitem__.side_effect = lambda key: {
            "azure_ai_resource_name": "test-resource",
            "azure_ai_project_name": "test-project",
            "agent_id": "static-agent-123",
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())

        url = handler._build_azure_url(None, None)

        assert "agent-id=static-agent-123" in url
        assert "test-resource" in url

    @patch("websocket_handler.config")
    @pytest.mark.asyncio
    async def test_send_initial_config_with_agent(self, mock_config):
        """Test sending initial configuration with agent config."""
        mock_config.__getitem__.side_effect = lambda key: {
            "model_deployment_name": "gpt-4o"
        }.get(key, "default")

        handler = VoiceProxyHandler(Mock())

        # Mock WebSocket
        mock_azure_ws = AsyncMock()

        agent_config = {
            "model": "gpt-4",
            "instructions": "Test instructions",
            "temperature": 0.8,
            "max_tokens": 1000,
        }

        await handler._send_initial_config(mock_azure_ws, agent_config)

        # Verify send was called
        mock_azure_ws.send.assert_called_once()

        # Parse the sent message
        sent_message = json.loads(mock_azure_ws.send.call_args[0][0])

        assert sent_message["type"] == "session.update"
        assert sent_message["session"]["instructions"] == "Test instructions"
        assert sent_message["session"]["temperature"] == 0.8
        assert sent_message["session"]["max_response_output_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_send_initial_config_without_agent(self):
        """Test sending initial configuration without agent config."""
        handler = VoiceProxyHandler(Mock())

        # Mock WebSocket
        mock_azure_ws = AsyncMock()

        await handler._send_initial_config(mock_azure_ws, None)

        # Verify send was called
        mock_azure_ws.send.assert_called_once()

        # Parse the sent message
        sent_message = json.loads(mock_azure_ws.send.call_args[0][0])

        assert sent_message["type"] == "session.update"
        assert "model" not in sent_message["session"]
        assert "instructions" not in sent_message["session"]

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending a message to WebSocket."""
        handler = VoiceProxyHandler(Mock())

        # Mock WebSocket with executor
        mock_ws = Mock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            message = {"type": "test", "data": "test data"}
            await handler._send_message(mock_ws, message)

            # Verify executor was called with correct arguments
            mock_loop.return_value.run_in_executor.assert_called_once()
            args = mock_loop.return_value.run_in_executor.call_args[0]
            assert args[0] is None  # executor
            assert args[1] == mock_ws.send  # function
            assert json.loads(args[2]) == message  # message
