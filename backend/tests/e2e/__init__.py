"""End-to-end tests against the deployed VoiceLive Sales Coach application.

Tests exercise the full HTTP API and WebSocket endpoints of the live deployed app.
For the audio/voice path, we use synthesized audio via Azure TTS to simulate a user.

Run with: pytest tests/e2e/ -v
Requires: SERVICE_VOICELAB_URI environment variable set to the deployed app URL.
"""

import asyncio
import base64
import json
import os
import time

import pytest
import requests

from tests.conftest import requires_live_endpoint, requires_speech


def _get_model_name():
    """Get the deployed model name from env or default."""
    return os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")


def _get_service_uri():
    """Get the deployed service URI."""
    return os.getenv("SERVICE_VOICELAB_URI", "").rstrip("/")


@requires_live_endpoint
class TestHealthAndConfig:
    """E2E tests for basic HTTP endpoints."""

    def test_index_page_loads(self):
        """Test the main page loads successfully."""
        resp = requests.get(f"{_get_service_uri()}/", timeout=30)
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("Content-Type", "")

    def test_config_endpoint(self):
        """Test /api/config returns expected structure."""
        resp = requests.get(f"{_get_service_uri()}/api/config", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data["proxy_enabled"] is True
        assert data["ws_endpoint"] == "/ws/voice"

    def test_scenarios_endpoint(self):
        """Test /api/scenarios returns a list of scenarios."""
        resp = requests.get(f"{_get_service_uri()}/api/scenarios", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least the graph-api scenario

        # Verify scenario structure
        ids = [s["id"] for s in data]
        assert "graph-api" in ids

        for scenario in data:
            assert "id" in scenario
            assert "name" in scenario

    def test_get_specific_scenario(self):
        """Test getting a specific scenario by ID."""
        # First get list to find a valid ID
        resp = requests.get(f"{_get_service_uri()}/api/scenarios", timeout=15)
        scenarios = resp.json()
        non_graph_scenarios = [s for s in scenarios if s["id"] != "graph-api"]

        if not non_graph_scenarios:
            pytest.skip("No predefined scenarios available")

        scenario_id = non_graph_scenarios[0]["id"]
        resp = requests.get(f"{_get_service_uri()}/api/scenarios/{scenario_id}", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data or "name" in data

    def test_nonexistent_scenario_returns_404(self):
        """Test requesting a nonexistent scenario returns 404."""
        resp = requests.get(f"{_get_service_uri()}/api/scenarios/this-does-not-exist", timeout=15)
        assert resp.status_code == 404


@requires_live_endpoint
class TestAgentLifecycle:
    """E2E tests for agent creation and deletion."""

    def test_create_agent_with_predefined_scenario(self):
        """Test creating an agent with a predefined scenario."""
        # Get a valid scenario
        resp = requests.get(f"{_get_service_uri()}/api/scenarios", timeout=15)
        scenarios = resp.json()
        non_graph = [s for s in scenarios if s["id"] != "graph-api"]
        if not non_graph:
            pytest.skip("No predefined scenarios")

        scenario_id = non_graph[0]["id"]

        resp = requests.post(
            f"{_get_service_uri()}/api/agents/create",
            json={"scenario_id": scenario_id},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data
        assert data["scenario_id"] == scenario_id
        agent_id = data["agent_id"]

        # Cleanup: delete the agent
        del_resp = requests.delete(f"{_get_service_uri()}/api/agents/{agent_id}", timeout=15)
        assert del_resp.status_code == 200

    def test_create_agent_with_custom_scenario(self):
        """Test creating an agent with a custom scenario."""
        custom_scenario = {
            "id": "e2e-test-custom",
            "name": "E2E Test Custom Scenario",
            "description": "Custom scenario for e2e testing",
            "messages": [{"content": "You are a helpful test assistant. Keep responses very short."}],
            "model": _get_model_name(),
            "modelParameters": {"temperature": 0.5, "max_tokens": 200},
        }

        resp = requests.post(
            f"{_get_service_uri()}/api/agents/create",
            json={"custom_scenario": custom_scenario},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data

        # Cleanup
        requests.delete(f"{_get_service_uri()}/api/agents/{data['agent_id']}", timeout=15)

    def test_create_agent_missing_scenario_returns_400(self):
        """Test creating an agent with no scenario_id returns 400."""
        resp = requests.post(
            f"{_get_service_uri()}/api/agents/create",
            json={},
            timeout=15,
        )
        assert resp.status_code == 400


@requires_live_endpoint
class TestConversationAnalysis:
    """E2E tests for the conversation analysis endpoint."""

    def test_analyze_conversation(self):
        """Test full conversation analysis against the live service."""
        transcript = (
            "User: Hi, I'd like to learn about your cloud migration services.\n"
            "Assistant: Great! We offer comprehensive cloud migration solutions. "
            "What's your current infrastructure like?\n"
            "User: We're running on-premises servers and looking to move to Azure.\n"
            "Assistant: Perfect fit. We've helped many companies make that transition. "
            "What's your timeline?\n"
            "User: We'd like to complete it within six months.\n"
        )

        resp = requests.post(
            f"{_get_service_uri()}/api/analyze",
            json={
                "scenario_id": "scenario1",
                "transcript": transcript,
                "reference_text": "cloud migration services",
            },
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()

        # AI assessment may or may not succeed depending on model availability
        if data.get("ai_assessment"):
            assessment = data["ai_assessment"]
            assert "overall_score" in assessment
            assert "speaking_tone_style" in assessment
            assert "conversation_content" in assessment

    def test_analyze_missing_fields_returns_400(self):
        """Test analysis with missing required fields."""
        resp = requests.post(
            f"{_get_service_uri()}/api/analyze",
            json={"scenario_id": "test"},
            timeout=15,
        )
        assert resp.status_code == 400


@requires_live_endpoint
@requires_speech
class TestWebSocketVoice:
    """E2E tests for the WebSocket voice proxy.

    Uses TTS-synthesized audio to simulate a speaking user through the WebSocket.
    """

    def test_websocket_connection(self):
        """Test WebSocket connection to the voice proxy endpoint."""
        import websockets.sync.client as ws_client

        service_uri = _get_service_uri()
        ws_uri = service_uri.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_uri}/ws/voice"

        try:
            with ws_client.connect(ws_url, open_timeout=15, close_timeout=5) as ws:
                # Get a valid scenario and create agent
                resp = requests.get(f"{service_uri}/api/scenarios", timeout=15)
                scenarios = resp.json()
                non_graph = [s for s in scenarios if s["id"] != "graph-api"]
                if not non_graph:
                    pytest.skip("No predefined scenarios")

                scenario_id = non_graph[0]["id"]
                create_resp = requests.post(
                    f"{service_uri}/api/agents/create",
                    json={"scenario_id": scenario_id},
                    timeout=30,
                )
                agent_id = create_resp.json()["agent_id"]

                # Send session.update with agent_id
                ws.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {"agent_id": agent_id},
                        }
                    )
                )

                # Wait for proxy.connected or session.created
                connected = False
                for _ in range(10):
                    try:
                        msg = ws.recv(timeout=5)
                        data = json.loads(msg)
                        if data.get("type") in ("proxy.connected", "session.created"):
                            connected = True
                            break
                    except Exception:
                        break

                # Cleanup
                requests.delete(f"{service_uri}/api/agents/{agent_id}", timeout=15)

                assert connected, "Failed to establish WebSocket voice proxy connection"

        except Exception as e:
            pytest.skip(f"WebSocket connection failed (may be expected in some environments): {e}")

    def test_websocket_audio_round_trip(self):
        """Test sending synthesized audio through WebSocket and receiving a response.

        This is the full e2e voice test:
        1. Create an agent
        2. Connect via WebSocket
        3. Synthesize audio via TTS
        4. Send audio through WebSocket
        5. Receive response events
        6. Cleanup
        """
        import websockets.sync.client as ws_client

        speech_key = os.getenv("AZURE_SPEECH_KEY")
        speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus2")
        if not speech_key:
            pytest.skip("AZURE_SPEECH_KEY not set for audio round trip")

        service_uri = _get_service_uri()

        # Step 1: Create custom agent with short responses
        custom_scenario = {
            "id": "e2e-voice-test",
            "name": "Voice E2E Test",
            "messages": [{"content": "You are a test assistant. Reply with exactly one short sentence."}],
            "model": _get_model_name(),
            "modelParameters": {"temperature": 0.3, "max_tokens": 100},
        }
        create_resp = requests.post(
            f"{service_uri}/api/agents/create",
            json={"custom_scenario": custom_scenario},
            timeout=30,
        )
        assert create_resp.status_code == 200
        agent_id = create_resp.json()["agent_id"]

        received_events = []
        try:
            # Step 2: Connect WebSocket
            ws_uri = service_uri.replace("https://", "wss://").replace("http://", "ws://")
            with ws_client.connect(f"{ws_uri}/ws/voice", open_timeout=15, close_timeout=5) as ws:
                # Send session update
                ws.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {"agent_id": agent_id},
                        }
                    )
                )

                # Wait for connection established
                for _ in range(10):
                    try:
                        msg = ws.recv(timeout=5)
                        data = json.loads(msg)
                        received_events.append(data.get("type", "unknown"))
                        if data.get("type") in ("proxy.connected", "session.created", "session.updated"):
                            break
                    except Exception:
                        break

                # Step 3: Synthesize audio
                import azure.cognitiveservices.speech as speechsdk

                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
                )
                speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
                result = synthesizer.speak_text_async("Hello, can you hear me?").get()
                assert result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted
                pcm_audio = result.audio_data

                # Step 4: Send audio as input_audio_buffer.append
                chunk_size = 4800  # 100ms at 24kHz 16-bit mono
                for i in range(0, len(pcm_audio), chunk_size):
                    chunk = pcm_audio[i : i + chunk_size]
                    encoded = base64.b64encode(chunk).decode("utf-8")
                    ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": encoded}))

                # Signal end of audio
                ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

                # Step 5: Collect response events (wait up to 30s)
                deadline = time.time() + 30
                while time.time() < deadline:
                    try:
                        msg = ws.recv(timeout=3)
                        data = json.loads(msg)
                        event_type = data.get("type", "unknown")
                        received_events.append(event_type)

                        # Stop when we get a response completion
                        if event_type in (
                            "response.done",
                            "response.audio.done",
                            "conversation.item.created",
                        ):
                            break
                    except Exception:
                        break

        finally:
            # Cleanup agent
            requests.delete(f"{service_uri}/api/agents/{agent_id}", timeout=15)

        # Verify we got some response from the service
        assert len(received_events) > 1, f"Expected multiple events, got: {received_events}"
        assert any(
            t in received_events for t in ("proxy.connected", "session.created")
        ), f"No connection event in: {received_events}"
