"""Flask application for the upskilling agent."""

import asyncio
import logging
import os
from flask import Flask, jsonify, request, send_from_directory
from flask_sock import Sock

from config import config
from services.managers import TokenManager, ScenarioManager, AgentManager
from services.analyzers import ConversationAnalyzer, PronunciationAssessor
from services.websocket_handler import VoiceProxyHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__, static_folder="../static", static_url_path="")
sock = Sock(app)

# Initialize managers and analyzers
token_manager = TokenManager()
scenario_manager = ScenarioManager()
agent_manager = AgentManager()
conversation_analyzer = ConversationAnalyzer()
pronunciation_assessor = PronunciationAssessor()
voice_proxy_handler = VoiceProxyHandler(token_manager, agent_manager)


@app.route("/")
def index():
    """Serve the main application page."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/config")
def get_config():
    """Get client configuration."""
    return jsonify({"proxy_enabled": True, "ws_endpoint": "/ws/voice"})


@app.route("/api/scenarios")
def get_scenarios():
    """Get list of available scenarios."""
    return jsonify(scenario_manager.list_scenarios())


@app.route("/api/scenarios/<scenario_id>")
def get_scenario(scenario_id):
    """Get a specific scenario by ID."""
    scenario = scenario_manager.get_scenario(scenario_id)
    if scenario:
        return jsonify(scenario)
    return jsonify({"error": "Scenario not found"}), 404


@app.route("/api/agents/create", methods=["POST"])
def create_agent():
    """Create a new agent for a scenario."""
    data = request.json
    scenario_id = data.get("scenario_id")

    if not scenario_id:
        return jsonify({"error": "scenario_id is required"}), 400

    scenario = scenario_manager.get_scenario(scenario_id)
    if not scenario:
        return jsonify({"error": "Scenario not found"}), 404

    try:
        agent_id = agent_manager.create_agent(scenario_id, scenario)
        return jsonify({"agent_id": agent_id, "scenario_id": scenario_id})
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    """Delete an agent."""
    try:
        agent_manager.delete_agent(agent_id)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze_conversation():
    """Analyze a conversation for performance assessment."""
    data = request.json
    scenario_id = data.get("scenario_id")
    transcript = data.get("transcript")
    audio_data = data.get("audio_data", [])

    logger.info(
        f"Analyze request - scenario: {scenario_id}, transcript length: {len(transcript or '')}"
    )

    if not scenario_id or not transcript:
        return jsonify({"error": "scenario_id and transcript are required"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        tasks = [
            conversation_analyzer.analyze_conversation(scenario_id, transcript),
            pronunciation_assessor.assess_pronunciation(audio_data, transcript),
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


@app.route("/audio-processor.js")
def audio_processor():
    """Serve the audio processor JavaScript file."""
    return send_from_directory("static", "audio-processor.js")


@sock.route("/ws/voice")
def voice_proxy(ws):
    """WebSocket endpoint for voice proxy."""
    logger.info("New WebSocket connection")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(voice_proxy_handler.handle_connection(ws))


def main():
    """Run the Flask application."""
    print(f"Starting Voice Live Demo on http://{config['host']}:{config['port']}")
    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.run(
        host=config["host"],
        port=config["port"],
        debug=debug_mode,
    )


if __name__ == "__main__":
    main()
