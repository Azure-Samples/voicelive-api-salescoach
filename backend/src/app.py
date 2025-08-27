# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""Flask application for the upskilling agent."""

import asyncio
import logging
import os
from typing import Any, Dict, List, cast
from flask import Flask, jsonify, request, send_from_directory
from flask_sock import Sock  # pyright: ignore[reportMissingTypeStubs]
import simple_websocket.ws  # pyright: ignore[reportMissingTypeStubs]

from config import config
from services.managers import ScenarioManager, AgentManager
from services.analyzers import ConversationAnalyzer, PronunciationAssessor
from services.websocket_handler import VoiceProxyHandler

# Constants
STATIC_FOLDER = "../static"
STATIC_URL_PATH = ""
INDEX_FILE = "index.html"
AUDIO_PROCESSOR_FILE = "audio-processor.js"
WEBSOCKET_ENDPOINT = "/ws/voice"

# API endpoints
API_CONFIG_ENDPOINT = "/api/config"
API_SCENARIOS_ENDPOINT = "/api/scenarios"
API_AGENTS_CREATE_ENDPOINT = "/api/agents/create"
API_ANALYZE_ENDPOINT = "/api/analyze"
API_GRAPH_SCENARIO_ENDPOINT = "/api/scenarios/graph"

# Error messages
SCENARIO_ID_REQUIRED = "scenario_id is required"
SCENARIO_NOT_FOUND = "Scenario not found"
TRANSCRIPT_REQUIRED = "scenario_id and transcript are required"

# HTTP status codes
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path=STATIC_URL_PATH)
sock = Sock(app)

# Initialize managers and analyzers
scenario_manager = ScenarioManager()
agent_manager = AgentManager()
conversation_analyzer = ConversationAnalyzer()
pronunciation_assessor = PronunciationAssessor()
voice_proxy_handler = VoiceProxyHandler(agent_manager)


@app.route("/")
def index():
    """Serve the main application page."""
    if app.static_folder is None:
        logger.error("STATIC_FOLDER is not set. Cannot serve index.html.")
        import sys

        sys.exit(1)
    return send_from_directory(app.static_folder, INDEX_FILE)


@app.route(API_CONFIG_ENDPOINT)
def get_config():
    """Get client configuration."""
    return jsonify({"proxy_enabled": True, "ws_endpoint": WEBSOCKET_ENDPOINT})


@app.route(API_SCENARIOS_ENDPOINT)
def get_scenarios():
    """Get list of available scenarios."""
    return jsonify(scenario_manager.list_scenarios())


@app.route(f"{API_SCENARIOS_ENDPOINT}/<scenario_id>")
def get_scenario(scenario_id: str):
    """Get a specific scenario by ID."""
    scenario = scenario_manager.get_scenario(scenario_id)
    if scenario:
        return jsonify(scenario)
    return jsonify({"error": SCENARIO_NOT_FOUND}), HTTP_NOT_FOUND


@app.route(API_AGENTS_CREATE_ENDPOINT, methods=["POST"])
def create_agent():
    """Create a new agent for a scenario."""
    data = cast(Dict[str, Any], request.json)
    scenario_id = data.get("scenario_id")

    if not scenario_id:
        return jsonify({"error": SCENARIO_ID_REQUIRED}), HTTP_BAD_REQUEST

    scenario = scenario_manager.get_scenario(scenario_id)
    if not scenario:
        logger.error(
            f"Scenario not found: {scenario_id}. Available scenarios: {list(scenario_manager.scenarios.keys())} + generated: {list(scenario_manager.generated_scenarios.keys())}"
        )
        return jsonify({"error": SCENARIO_NOT_FOUND}), HTTP_NOT_FOUND

    try:
        agent_id = agent_manager.create_agent(scenario_id, scenario)
        return jsonify({"agent_id": agent_id, "scenario_id": scenario_id})
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return jsonify({"error": str(e)}), HTTP_INTERNAL_SERVER_ERROR


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id: str):
    """Delete an agent."""
    try:
        agent_manager.delete_agent(agent_id)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        return jsonify({"error": str(e)}), HTTP_INTERNAL_SERVER_ERROR


@app.route(API_ANALYZE_ENDPOINT, methods=["POST"])
def analyze_conversation():
    """Analyze a conversation for performance assessment."""
    data = cast(Dict[str, Any], request.json)
    scenario_id = cast(str, data.get("scenario_id"))
    transcript = cast(str, data.get("transcript"))
    audio_data = data.get("audio_data", [])
    reference_text = cast(str, data.get("reference_text"))

    _log_analyze_request(scenario_id, transcript, reference_text)

    if not scenario_id or not transcript:
        return jsonify({"error": TRANSCRIPT_REQUIRED}), HTTP_BAD_REQUEST

    return _perform_conversation_analysis(
        scenario_id, transcript, audio_data, reference_text
    )


def _log_analyze_request(scenario_id: str, transcript: str, reference_text: str):
    """Log information about the analyze request."""
    logger.info(
        f"Analyze request - scenario: {scenario_id}, "
        f"transcript length: {len(transcript or '')}, "
        f"reference_text length: {len(reference_text or '')}"
    )


def _perform_conversation_analysis(
    scenario_id: str,
    transcript: str,
    audio_data: List[Dict[str, Any]],
    reference_text: str,
):
    """Perform the actual conversation analysis."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        tasks = [
            conversation_analyzer.analyze_conversation(scenario_id, transcript),
            pronunciation_assessor.assess_pronunciation(audio_data, reference_text),
        ]

        results = loop.run_until_complete(
            asyncio.gather(*tasks, return_exceptions=True)
        )

        ai_assessment, pronunciation = results

        if isinstance(ai_assessment, Exception):
            logger.error(f"AI assessment failed: {ai_assessment}")
            ai_assessment = None

        if isinstance(pronunciation, Exception):
            logger.error(f"Pronunciation assessment failed: {pronunciation}")
            pronunciation = None

        return jsonify(
            {"ai_assessment": ai_assessment, "pronunciation_assessment": pronunciation}
        )

    finally:
        loop.close()


@app.route(f"/{AUDIO_PROCESSOR_FILE}")
def audio_processor():
    """Serve the audio processor JavaScript file."""
    return send_from_directory("static", AUDIO_PROCESSOR_FILE)


@sock.route(WEBSOCKET_ENDPOINT)  # pyright: ignore[reportUnknownMemberType]
def voice_proxy(ws: simple_websocket.ws.Server):
    """WebSocket endpoint for voice proxy."""

    logger.info("New WebSocket connection")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(voice_proxy_handler.handle_connection(ws))


@app.route(API_GRAPH_SCENARIO_ENDPOINT, methods=["POST"])
def generate_graph_scenario():
    """Generate a scenario based on Graph API data."""
    import time
    import json
    from pathlib import Path

    # Simulate API delay
    time.sleep(2)

    try:
        docker_canned_file = Path("/app/data/graph-api-canned.json")
        dev_canned_file = (
            Path(__file__).parent.parent.parent / "data" / "graph-api-canned.json"
        )

        canned_file = (
            docker_canned_file if docker_canned_file.exists() else dev_canned_file
        )

        if not canned_file.exists():
            logger.error(f"Canned Graph API file not found at {canned_file}")
            graph_data: Dict[str, Any] = {"value": []}
        else:
            with open(canned_file) as f:
                graph_data = json.load(f)

        scenario = scenario_manager.generate_scenario_from_graph(graph_data)

        return jsonify(scenario)
    except Exception as e:
        logger.error(f"Failed to generate Graph scenario: {e}")
        return jsonify({"error": str(e)}), HTTP_INTERNAL_SERVER_ERROR


def main():
    """Run the Flask application."""
    host = config["host"]
    port = config["port"]
    print(f"Starting Voice Live Demo on http://{host}:{port}")

    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.run(host=host, port=port, debug=debug_mode)


if __name__ == "__main__":
    main()
