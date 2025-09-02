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

from config import config
from services.managers import AgentManager

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

# Function calling constants
END_CONVERSATION_FUNCTION_NAME = "end_conversation"

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

    async def _get_agent_id_from_client(
        self, client_ws: simple_websocket.ws.Server
    ) -> Optional[str]:
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
            logger.error(f"Error getting agent ID: {e}")
            return None

    async def _connect_to_azure(
        self, agent_id: Optional[str]
    ) -> Optional[websockets.asyncio.client.ClientConnection]:
        """Connect to Azure Voice API with appropriate configuration."""
        try:
            agent_config = self.agent_manager.get_agent(agent_id) if agent_id else None

            azure_url = self._build_azure_url(agent_id, agent_config)

            api_key = config.get("azure_openai_api_key")
            if not api_key:
                logger.error("No API key found in configuration (azure_openai_api_key)")
                return None

            headers = {"api-key": api_key}

            azure_ws = await websockets.connect(azure_url, additional_headers=headers)
            logger.info(
                f"Connected to Azure Voice API with agent: {agent_id or 'default'}"
            )

            await self._send_initial_config(azure_ws, agent_config)

            return azure_ws

        except Exception as e:
            logger.error(f"Failed to connect to Azure: {e}")
            return None

    def _build_azure_url(
        self, agent_id: Optional[str], agent_config: Optional[Dict[str, Any]]
    ) -> str:
        """Build the Azure WebSocket URL."""
        base_url = self._build_base_azure_url()

        if agent_config:
            return self._build_agent_specific_url(base_url, agent_id, agent_config)
        elif config["agent_id"]:
            return f"{base_url}&agent-id={config['agent_id']}"
        else:
            model_name = config["model_deployment_name"]
            return f"{base_url}&model={model_name}"

    def _build_base_azure_url(self) -> str:
        """Build the base Azure WebSocket URL."""
        resource_name = config["azure_ai_resource_name"]
        project_name = config["azure_ai_project_name"]
        client_request_id = uuid.uuid4()

        return (
            f"wss://{resource_name}.{AZURE_COGNITIVE_SERVICES_DOMAIN}/"
            f"{VOICE_AGENT_ENDPOINT}?api-version={AZURE_VOICE_API_VERSION}"
            f"&x-ms-client-request-id={client_request_id}"
            f"&agent-project-name={project_name}"
        )

    def _build_agent_specific_url(
        self, base_url: str, agent_id: Optional[str], agent_config: Dict[str, Any]
    ) -> str:
        """Build URL for specific agent configuration."""
        if agent_config.get("is_azure_agent"):
            return f"{base_url}&agent-id={agent_id}"
        else:
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
                "input_audio_echo_cancellation": {
                    "type": DEFAULT_ECHO_CANCELLATION_TYPE
                },
                "avatar": {
                    "character": DEFAULT_AVATAR_CHARACTER,
                    "style": DEFAULT_AVATAR_STYLE,
                },
                "tools": [
                    {
                        "type": "function",
                        "name": END_CONVERSATION_FUNCTION_NAME,
                        "description": "End the conversation when it becomes unprofessional, inappropriate, or abusive. Use this to professionally conclude the interaction.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "description": "Brief professional reason for ending the conversation"
                                }
                            },
                            "required": ["reason"]
                        }
                    }
                ],
                "tool_choice": "auto"
            },
        }

    def _add_local_agent_config(
        self, config_message: Dict[str, Any], agent_config: Dict[str, Any]
    ) -> None:
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
            asyncio.create_task(self._forward_azure_to_client_with_functions(azure_ws, client_ws)),
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
                logger.debug(f"Client->Azure: {message[:LOG_MESSAGE_MAX_LENGTH]}")
                await azure_ws.send(message)
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _forward_azure_to_client_with_functions(
        self,
        azure_ws: websockets.asyncio.client.ClientConnection,
        client_ws: simple_websocket.ws.Server,
    ) -> None:
        """Forward messages from Azure to client with function call handling."""
        try:
            async for message in azure_ws:
                logger.debug(f"Azure->Client: {message[:LOG_MESSAGE_MAX_LENGTH]}")
                
                # Check if this is a function call
                try:
                    msg_data = json.loads(message)
                    if msg_data.get("type") == "response.function_call_arguments.done":
                        await self._handle_function_call(msg_data, azure_ws)
                except json.JSONDecodeError:
                    pass
                
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    client_ws.send,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
                    message,
                )
        except Exception:
            logger.debug("Client connection closed during forwarding")

    async def _handle_function_call(
        self,
        msg_data: Dict[str, Any],
        azure_ws: websockets.asyncio.client.ClientConnection,
    ) -> None:
        """Handle function calls from the agent."""
        call_id = msg_data.get("call_id")
        arguments_str = msg_data.get("arguments", "{}")
        
        try:
            arguments = json.loads(arguments_str)
            if msg_data.get("item_id"):
                # Get the function name from the function call item
                # For now, we'll assume it's the end_conversation function
                function_name = END_CONVERSATION_FUNCTION_NAME
                
                if function_name == END_CONVERSATION_FUNCTION_NAME:
                    reason = arguments.get("reason", "Conversation ended by agent")
                    logger.info(f"Agent ending conversation: {reason}")
                    
                    # Send function call output back to Azure
                    function_output = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps({
                                "success": True,
                                "message": f"Conversation ended professionally. Reason: {reason}"
                            })
                        }
                    }
                    await azure_ws.send(json.dumps(function_output))
                    
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing function arguments: {e}")
        except Exception as e:
            logger.error(f"Error handling function call: {e}")

    async def _send_message(
        self, ws: simple_websocket.ws.Server, message: Dict[str, str | Dict[str, str]]
    ) -> None:
        """Send a JSON message to a WebSocket."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                ws.send,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType]
                json.dumps(message),
            )
        except Exception:
            pass

    async def _send_error(
        self, ws: simple_websocket.ws.Server, error_message: str
    ) -> None:
        """Send an error message to a WebSocket."""

        await self._send_message(
            ws, {"type": "error", "error": {"message": error_message}}
        )
        """Send an error message to a WebSocket."""
        await self._send_message(
            ws, {"type": "error", "error": {"message": error_message}}
        )
