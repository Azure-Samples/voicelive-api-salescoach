# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""WebSocket handling for voice proxy connections."""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

import simple_websocket.ws  # pyright: ignore[reportMissingTypeStubs]
import websockets
import websockets.asyncio.client
from azure.identity import DefaultAzureCredential

from src.config import config
from src.services.managers import AgentManager

logger = logging.getLogger(__name__)

# WebSocket constants
AZURE_VOICE_API_VERSION = "2025-05-01-preview"
AZURE_COGNITIVE_SERVICES_DOMAIN = "cognitiveservices.azure.com"
VOICE_AGENT_ENDPOINT = "voice-agent/realtime"

# Session configuration constants
DEFAULT_MODALITIES = ["text", "audio"]
DEFAULT_TURN_DETECTION_TYPE = "azure_semantic_vad"
DEFAULT_NOISE_REDUCTION_TYPE = "azure_deep_noise_suppression"
DEFAULT_ECHO_CANCELLATION_TYPE = "server_echo_cancellation"
DEFAULT_AVATAR_CHARACTER = "lisa"
DEFAULT_AVATAR_STYLE = "casual-sitting"
DEFAULT_VOICE_NAME = "en-US-Ava:DragonHDLatestNeural"
DEFAULT_VOICE_TYPE = "azure-standard"

# Message types
SESSION_UPDATE_TYPE = "session.update"
PROXY_CONNECTED_TYPE = "proxy.connected"
ERROR_TYPE = "error"

# Log message truncation length
LOG_MESSAGE_MAX_LENGTH = 100


class VoiceProxyHandler:
    """Handles WebSocket proxy connections between client and Azure Voice API."""

    def __init__(self, agent_manager: AgentManager):
        """
        Initialize the voice proxy handler.

        Args:
            agent_manager: Agent manager instance
        """
        self.agent_manager = agent_manager

    async def handle_connection(self, client_ws: simple_websocket.ws.Server) -> None:
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
                await self._send_error(client_ws, "Failed to connect to Azure Voice API")
                return

            await self._send_message(
                client_ws,
                {"type": "proxy.connected", "message": "Connected to Azure Voice API"},
            )

            await self._handle_message_forwarding(client_ws, azure_ws)

        except Exception as e:
            logger.error("Proxy error: %s", e)
            await self._send_error(client_ws, str(e))

        finally:
            if azure_ws:
                await azure_ws.close()

    async def _get_agent_id_from_client(self, client_ws: simple_websocket.ws.Server) -> Optional[str]:
        """Get agent ID from initial client message."""

        try:
            first_message: str | None = await asyncio.get_event_loop().run_in_executor(
                None,
                client_ws.receive,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
            )
            if first_message:
                msg = json.loads(first_message)
                if msg.get("type") == "session.update":
                    return msg.get("session", {}).get("agent_id")
        except Exception as e:
            logger.error("Error getting agent ID: %s", e)
            return None

    async def _connect_to_azure(self, agent_id: Optional[str]) -> Optional[websockets.asyncio.client.ClientConnection]:
        """Connect to Azure Voice API with appropriate configuration."""
        try:
            agent_config = self.agent_manager.get_agent(agent_id) if agent_id else None

            # Determine whether this is an Azure Agent (Bearer) or local/model (api-key) flow
            is_azure_agent = bool(agent_config and agent_config.get("is_azure_agent"))

            api_key = config.get("azure_openai_api_key")
            token_value: Optional[str] = None
            if is_azure_agent or config.get("agent_id"):
                # Attempt to acquire AAD token (best effort); fall back to API key if present
                scopes = "https://ai.azure.com/.default"
                try:
                    token_credential = DefaultAzureCredential()
                    token = token_credential.get_token(scopes)
                    token_value = token.token
                except Exception as token_err:  # pragma: no cover - network/identity issues
                    logger.warning("Failed to acquire Azure AD token, will fall back to api-key if available: %s", token_err)

            # Build headers preference: Bearer token if we have one, else API key
            headers: Dict[str, str]
            if token_value:
                headers = {"Authorization": f"Bearer {token_value}"}
            else:
                if not api_key:
                    logger.error(
                        "No authentication method available: missing both Azure AD token and azure_openai_api_key"
                    )
                    return None
                headers = {"api-key": api_key}

            azure_url = self._build_azure_url(agent_id, agent_config, token_value)

            azure_ws = await websockets.connect(azure_url, additional_headers=headers)
            logger.info(
                "Connected to Azure Voice API with agent: %s (auth=%s)",
                agent_id or "default",
                "bearer" if token_value else "api-key",
            )

            await self._send_initial_config(azure_ws, agent_config)

            return azure_ws

        except Exception as e:  # broad catch to ensure we surface connection failures gracefully
            logger.error("Failed to connect to Azure: %s", e)
            return None

    def _build_azure_url(
        self, agent_id: Optional[str], agent_config: Optional[Dict[str, Any]], token: Optional[str] = None
    ) -> str:
        """Build the Azure WebSocket URL."""
        base_url = self._build_base_azure_url()
        project_name = config["azure_ai_project_name"]

        if agent_config:
            return self._build_agent_specific_url(base_url, agent_id, agent_config, token)
        if config["agent_id"]:
            # Only append access token parameter if we actually have one
            access_token_param = f"&agent-access-token={token}" if token else ""
            return (
                f"{base_url}&agent-id={config['agent_id']}" f"&agent-project-name={project_name}{access_token_param}"
            )
        model_name = config["model_deployment_name"]
        return f"{base_url}&model={model_name}"

    def _build_base_azure_url(self) -> str:
        """Build the base Azure WebSocket URL."""
        resource_name = config["azure_ai_resource_name"]

        client_request_id = uuid.uuid4()

        return (
            f"wss://{resource_name}.{AZURE_COGNITIVE_SERVICES_DOMAIN}/"
            f"{VOICE_AGENT_ENDPOINT}?api-version={AZURE_VOICE_API_VERSION}"
            f"&x-ms-client-request-id={client_request_id}"
        )

    def _build_agent_specific_url(
        self, base_url: str, agent_id: Optional[str], agent_config: Dict[str, Any], token: Optional[str]
    ) -> str:
        """Build URL for specific agent configuration."""
        project_name = config["azure_ai_project_name"]
        if agent_config.get("is_azure_agent"):
            access_token_param = f"&agent-access-token={token}" if token else ""
            return f"{base_url}&agent-id={agent_id}" f"&agent-project-name={project_name}{access_token_param}"
        model_name = agent_config.get("model", config["model_deployment_name"])
        return f"{base_url}&model={model_name}"

    async def _send_initial_config(
        self,
        azure_ws: websockets.asyncio.client.ClientConnection,
        agent_config: Optional[Dict[str, Any]],
    ) -> None:
        """Send initial configuration to Azure."""
        config_message = self._build_session_config()

        if agent_config and not agent_config.get("is_azure_agent"):
            self._add_local_agent_config(config_message, agent_config)

        await azure_ws.send(json.dumps(config_message))

    def _build_session_config(self) -> Dict[str, Any]:
        """Build the base session configuration."""
        return {
            "type": SESSION_UPDATE_TYPE,
            "session": {
                "modalities": DEFAULT_MODALITIES,
                "turn_detection": {"type": DEFAULT_TURN_DETECTION_TYPE},
                "input_audio_noise_reduction": {"type": DEFAULT_NOISE_REDUCTION_TYPE},
                "input_audio_echo_cancellation": {"type": DEFAULT_ECHO_CANCELLATION_TYPE},
                "avatar": {
                    "character": DEFAULT_AVATAR_CHARACTER,
                    "style": DEFAULT_AVATAR_STYLE,
                },
                "voice": {
                    "name": config["azure_voice_name"],
                    "type": config["azure_voice_type"],
                },
            },
        }

    def _add_local_agent_config(self, config_message: Dict[str, Any], agent_config: Dict[str, Any]) -> None:
        """Add local agent configuration to session config."""
        session = config_message["session"]
        session["model"] = agent_config.get("model", config["model_deployment_name"])
        session["instructions"] = agent_config["instructions"]
        session["temperature"] = agent_config["temperature"]
        session["max_response_output_tokens"] = agent_config["max_tokens"]

    async def _handle_message_forwarding(
        self,
        client_ws: simple_websocket.ws.Server,
        azure_ws: websockets.asyncio.client.ClientConnection,
    ) -> None:
        """Handle bidirectional message forwarding."""
        tasks = [
            asyncio.create_task(self._forward_client_to_azure(client_ws, azure_ws)),
            asyncio.create_task(self._forward_azure_to_client(azure_ws, client_ws)),
        ]

        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    async def _forward_client_to_azure(
        self,
        client_ws: simple_websocket.ws.Server,
        azure_ws: websockets.asyncio.client.ClientConnection,
    ) -> None:
        """Forward messages from client to Azure."""
        try:
            while True:
                message: Optional[Any] = await asyncio.get_event_loop().run_in_executor(
                    None,
                    client_ws.receive,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
                )
                if message is None:
                    break
                logger.debug("Client->Azure: %s", message[:LOG_MESSAGE_MAX_LENGTH])
                await azure_ws.send(message)
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _forward_azure_to_client(
        self,
        azure_ws: websockets.asyncio.client.ClientConnection,
        client_ws: simple_websocket.ws.Server,
    ) -> None:
        """Forward messages from Azure to client."""
        try:
            async for message in azure_ws:
                logger.debug("Azure->Client: %s", message[:LOG_MESSAGE_MAX_LENGTH])
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    client_ws.send,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
                    message,
                )
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _send_message(self, ws: simple_websocket.ws.Server, message: Dict[str, str | Dict[str, str]]) -> None:
        """Send a JSON message to a WebSocket."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                ws.send,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
                json.dumps(message),
            )
        except Exception:
            pass

    async def _send_error(self, ws: simple_websocket.ws.Server, error_message: str) -> None:
        """Send an error message to a WebSocket."""
        await self._send_message(ws, {"type": "error", "error": {"message": error_message}})
