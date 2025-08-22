"""WebSocket handling for voice proxy connections."""

import asyncio
import json
import logging
import uuid
from typing import Optional

import websockets

from config import config
from services.managers import AgentManager

logger = logging.getLogger(__name__)


class VoiceProxyHandler:
    """Handles WebSocket proxy connections between client and Azure Voice API."""

    def __init__(self, token_manager, agent_manager: AgentManager):
        """
        Initialize the voice proxy handler.

        Args:
            token_manager: Token manager instance (kept for compatibility but not used)
            agent_manager: Agent manager instance
        """
        # Keep token_manager parameter for compatibility but don't use it
        self.agent_manager = agent_manager

    async def handle_connection(self, client_ws) -> None:
        """
        Handle a WebSocket connection from a client.

        Args:
            client_ws: The client WebSocket connection
        """
        azure_ws = None
        current_agent_id = None

        try:
            current_agent_id = await self._get_agent_id_from_client(client_ws)

            azure_ws = await self._connect_to_azure(current_agent_id)

            if not azure_ws:
                await self._send_error(
                    client_ws, "Failed to connect to Azure Voice API"
                )
                return

            await self._send_message(
                client_ws,
                {"type": "proxy.connected", "message": "Connected to Azure Voice API"},
            )

            await self._handle_message_forwarding(client_ws, azure_ws)

        except Exception as e:
            logger.error(f"Proxy error: {e}")
            await self._send_error(client_ws, str(e))

        finally:
            if azure_ws:
                await azure_ws.close()

    async def _get_agent_id_from_client(self, client_ws) -> Optional[str]:
        """Get agent ID from initial client message."""
        try:
            first_message = await asyncio.get_event_loop().run_in_executor(
                None, client_ws.receive
            )
            if first_message:
                msg = json.loads(first_message)
                if msg.get("type") == "session.update":
                    return msg.get("session", {}).get("agent_id")
        except Exception as e:
            logger.error(f"Error getting agent ID: {e}")
        return None

    async def _connect_to_azure(
        self, agent_id: Optional[str]
    ) -> Optional[websockets.WebSocketClientProtocol]:
        """Connect to Azure Voice API with appropriate configuration."""
        try:
            agent_config = self.agent_manager.get_agent(agent_id) if agent_id else None

            azure_url = self._build_azure_url(agent_id, agent_config)

            api_key = config.get("azure_openai_api_key")
            if not api_key:
                logger.error("No API key found in configuration (azure_openai_api_key)")
                return None

            headers = {"api-key": api_key}

            azure_ws = await websockets.connect(azure_url, extra_headers=headers)
            logger.info(
                f"Connected to Azure Voice API with agent: {agent_id or 'default'}"
            )

            await self._send_initial_config(azure_ws, agent_config)

            return azure_ws

        except Exception as e:
            logger.error(f"Failed to connect to Azure: {e}")
            return None

    def _build_azure_url(
        self, agent_id: Optional[str], agent_config: Optional[dict]
    ) -> str:
        """Build the Azure WebSocket URL."""
        base_url = (
            f"wss://{config['azure_ai_resource_name']}.cognitiveservices.azure.com/"
            f"voice-agent/realtime?api-version=2025-05-01-preview"
            f"&x-ms-client-request-id={uuid.uuid4()}"
            f"&agent-project-name={config['azure_ai_project_name']}"
        )

        if agent_config:
            if agent_config.get("is_azure_agent"):
                return f"{base_url}&agent-id={agent_id}"
            else:
                model_name = agent_config.get("model", config["model_deployment_name"])
                return f"{base_url}&model={model_name}"
        elif config["agent_id"]:
            return f"{base_url}&agent-id={config['agent_id']}"
        else:
            model_name = config["model_deployment_name"]
            return f"{base_url}&model={model_name}"

    async def _send_initial_config(
        self, azure_ws, agent_config: Optional[dict]
    ) -> None:
        """Send initial configuration to Azure."""
        config_message = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "turn_detection": {"type": "azure_semantic_vad"},
                "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
                "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
                "avatar": {"character": "lisa", "style": "casual-sitting"},
            },
        }

        if agent_config and not agent_config.get("is_azure_agent"):
            config_message["session"]["model"] = agent_config.get(
                "model", config["model_deployment_name"]
            )
            config_message["session"]["instructions"] = agent_config["instructions"]
            config_message["session"]["temperature"] = agent_config["temperature"]
            config_message["session"]["max_response_output_tokens"] = agent_config[
                "max_tokens"
            ]

        await azure_ws.send(json.dumps(config_message))

    async def _handle_message_forwarding(self, client_ws, azure_ws) -> None:
        """Handle bidirectional message forwarding."""
        tasks = [
            asyncio.create_task(self._forward_client_to_azure(client_ws, azure_ws)),
            asyncio.create_task(self._forward_azure_to_client(azure_ws, client_ws)),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    async def _forward_client_to_azure(self, client_ws, azure_ws) -> None:
        """Forward messages from client to Azure."""
        try:
            while True:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, client_ws.receive
                )
                if message is None:
                    break
                logger.debug(f"Client->Azure: {message[:100]}")
                await azure_ws.send(message)
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _forward_azure_to_client(self, azure_ws, client_ws) -> None:
        """Forward messages from Azure to client."""
        try:
            async for message in azure_ws:
                logger.debug(f"Azure->Client: {message[:100]}")
                await asyncio.get_event_loop().run_in_executor(
                    None, client_ws.send, message
                )
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _send_message(self, ws, message: dict) -> None:
        """Send a JSON message to a WebSocket."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, ws.send, json.dumps(message)
            )
        except Exception:
            pass

    async def _send_error(self, ws, error_message: str) -> None:
        """Send an error message to a WebSocket."""
        await self._send_message(
            ws, {"type": "error", "error": {"message": error_message}}
        )
        """Send an error message to a WebSocket."""
        await self._send_message(
            ws, {"type": "error", "error": {"message": error_message}}
        )
