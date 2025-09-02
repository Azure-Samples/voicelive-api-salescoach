# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""Business logic managers for the upskilling agent application."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from src.config import config
from src.services.graph_scenario_generator import GraphScenarioGenerator
from src.services.scenario_utils import determine_scenario_directory

# Constants
ROLE_PLAY_FILE_SUFFIX = "-role-play.prompt.yml"
ROLE_PLAY_SUFFIX_REMOVAL = "-role-play.prompt"
AGENT_ID_PREFIX = "local-agent"
AZURE_AGENT_NAME_PREFIX = "agent"
UUID_SHORT_LENGTH = 8
MAX_RESPONSE_LENGTH_SENTENCES = 3
SCENARIO_DATA_DIR = "data/scenarios"
DOCKER_APP_PATH = "/app"

logger = logging.getLogger(__name__)


class ScenarioManager:
    """Manages training scenarios loaded from YAML files."""

    def __init__(self, scenario_dir: Optional[Path] = None):
        """
        Initialize the scenario manager.

        Args:
            scenario_dir: Directory containing scenario YAML files
        """
        self.scenario_dir = determine_scenario_directory(scenario_dir)
        self.scenarios = self._load_scenarios()
        self.graph_generator = GraphScenarioGenerator()
        self.generated_scenarios: Dict[str, Any] = {}

    def _load_scenarios(self) -> Dict[str, Any]:
        """
        Load scenarios from YAML files.

        Returns:
            Dict[str, Any]: Dictionary of scenarios keyed by ID
        """
        scenarios: Dict[str, Any] = {}

        if not self.scenario_dir.exists():
            logger.warning("Scenarios directory not found: %s", self.scenario_dir)
            return scenarios

        for file in self.scenario_dir.glob(f"*{ROLE_PLAY_FILE_SUFFIX}"):
            scenario_id = self._extract_scenario_id(file)
            scenario = self._load_scenario_file(file)
            if scenario:
                scenarios[scenario_id] = scenario
                logger.info("Loaded scenario: %s", scenario_id)

        logger.info("Total scenarios loaded: %s", len(scenarios))
        return scenarios

    def _extract_scenario_id(self, file: Path) -> str:
        """Extract scenario ID from filename."""
        return file.stem.replace(ROLE_PLAY_SUFFIX_REMOVAL, "")

    def _load_scenario_file(self, file: Path) -> Optional[Dict[str, Any]]:
        """Load a single scenario file."""
        try:
            with open(file, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error("Error loading scenario %s: %s", file, e)
            return None

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific scenario by ID.

        Args:
            scenario_id: The scenario identifier

        Returns:
            Optional[Dict[str, Any]]: Scenario data or None if not found
        """
        scenario = self.scenarios.get(scenario_id)
        if scenario:
            return scenario

        return self.generated_scenarios.get(scenario_id)

    def list_scenarios(self) -> List[Dict[str, str | bool]]:
        """
        List all available scenarios.

        Returns:
            List[Dict[str, str]]: List of scenario summaries
        """
        scenarios: List[Dict[str, str | bool]] = [
            {
                "id": scenario_id,
                "name": scenario_data.get("name", "Unknown"),
                "description": scenario_data.get("description", ""),
            }
            for scenario_id, scenario_data in self.scenarios.items()
        ]

        scenarios.append(
            {
                "id": "graph-api",
                "name": "Personalized Scenario",
                "description": "AI-generated scenario based on your upcoming meetings and context from Microsoft Graph",
                "is_graph_scenario": True,
            }
        )

        return scenarios

    def generate_scenario_from_graph(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a scenario based on Microsoft Graph API data.

        Args:
            graph_data: The Graph API response data

        Returns:
            Dict[str, Any]: Generated scenario
        """
        scenario = self.graph_generator.generate_scenario_from_graph(graph_data)

        self.generated_scenarios[scenario["id"]] = scenario

        return scenario


class AgentManager:
    """Manages virtual training agents."""

    # Base instructions for human-like interactions
    BASE_INSTRUCTIONS = f"""

CRITICAL INTERACTION GUIDELINES:
- Keep responses SHORT and conversational ({MAX_RESPONSE_LENGTH_SENTENCES} sentences max, as if speaking on phone)
- ALWAYS stay in character - never break role or acknowledge you're an AI
- Simulate natural human speech patterns with pauses, "um", "well", occasional hesitation
- Respond as a real person would in this business context
- Use natural phone conversation style - direct, clear, but personable
- Show genuine human emotions and reactions appropriate to the situation
- Ask follow-up questions to keep the conversation flowing naturally
- Avoid overly formal or robotic language - speak like a real business professional would
    """

    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.credential = DefaultAzureCredential()
        self.use_azure_ai_agents = config["use_azure_ai_agents"]
        self.project_client = self._initialize_project_client()
        self._log_initialization_status()

    def _log_initialization_status(self) -> None:
        """Log the initialization status of the agent manager."""
        if self.use_azure_ai_agents:
            logger.info("AgentManager initialized with Azure AI Agent Service support")
        else:
            logger.info("AgentManager initialized with instruction-based approach only")

    def _initialize_project_client(self) -> Optional[AIProjectClient]:
        """Initialize the Azure AI Project client."""
        try:
            project_endpoint = config["project_endpoint"]
            if not project_endpoint:
                logger.warning("PROJECT_ENDPOINT not configured - falling back to instruction-based approach")
                return None

            client = AIProjectClient(
                endpoint=project_endpoint,
                credential=self.credential,
            )
            logger.info("AI Project client initialized with endpoint: %s", project_endpoint)
            return client
        except Exception as e:
            logger.error("Failed to initialize AI Project client: %s", e)
            return None

    def create_agent(self, scenario_id: str, scenario_data: Dict[str, Any]) -> str:
        """
        Create a new virtual agent for a scenario.

        Args:
            scenario_id: The scenario identifier
            scenario_data: The scenario configuration data

        Returns:
            str: The created agent's ID

        Raises:
            Exception: If agent creation fails
        """

        scenario_instructions = scenario_data.get("messages", [{}])[0].get("content", "")
        combined_instructions = scenario_instructions + self.BASE_INSTRUCTIONS

        model_name = scenario_data.get("model", config["model_deployment_name"])
        temperature = scenario_data.get("modelParameters", {}).get("temperature", 0.7)
        max_tokens = scenario_data.get("modelParameters", {}).get("max_tokens", 2000)

        if self.use_azure_ai_agents and self.project_client:
            return self._create_azure_agent(scenario_id, combined_instructions, model_name, temperature, max_tokens)
        return self._create_local_agent(scenario_id, combined_instructions, model_name, temperature, max_tokens)

    def _create_azure_agent(
        self,
        scenario_id: str,
        instructions: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Create an agent using Azure AI Agent Service."""

        if not self.project_client:
            logger.warning("Project client not available, using fallback scenario")
            return ""
        project_client = self.project_client

        try:
            with project_client:
                agent_name = self._generate_agent_name(scenario_id)
                agent = project_client.agents.create_agent(
                    model=model,
                    name=agent_name,
                    instructions=instructions,
                    tools=[],
                    temperature=temperature,
                )

                agent_id = agent.id
                logger.info("Created Azure AI agent: %s", agent_id)

                self.agents[agent_id] = self._create_agent_config(
                    scenario_id=scenario_id,
                    agent_id=agent_id,
                    is_azure_agent=True,
                    instructions=instructions,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                return agent_id

        except Exception as e:
            logger.error("Error creating Azure agent: %s", e)
            raise

    def _create_local_agent(
        self,
        scenario_id: str,
        instructions: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Create a local agent configuration without Azure AI Agent Service."""
        try:
            agent_id = self._generate_local_agent_id(scenario_id)

            self.agents[agent_id] = self._create_agent_config(
                scenario_id=scenario_id,
                agent_id=agent_id,
                is_azure_agent=False,
                instructions=instructions,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            logger.info("Created local agent configuration: %s", agent_id)
            return agent_id

        except Exception as e:
            logger.error("Error creating local agent: %s", e)
            raise

    def _generate_agent_name(self, scenario_id: str) -> str:
        """Generate a unique agent name."""
        short_uuid = uuid.uuid4().hex[:UUID_SHORT_LENGTH]
        return f"{AZURE_AGENT_NAME_PREFIX}-{scenario_id}-{short_uuid}"

    def _generate_local_agent_id(self, scenario_id: str) -> str:
        """Generate a unique local agent ID."""
        short_uuid = uuid.uuid4().hex[:UUID_SHORT_LENGTH]
        return f"{AGENT_ID_PREFIX}-{scenario_id}-{short_uuid}"

    def _create_agent_config(
        self,
        scenario_id: str,
        agent_id: str,
        is_azure_agent: bool,
        instructions: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Create standardized agent configuration."""
        result: Dict[str, Any] = {
            "scenario_id": scenario_id,
            "is_azure_agent": is_azure_agent,
            "instructions": instructions,
            "created_at": datetime.now(),
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if is_azure_agent:
            result["azure_agent_id"] = agent_id

        return result

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent configuration by ID.

        Args:
            agent_id: The agent identifier

        Returns:
            Optional[Dict[str, Any]]: Agent configuration or None if not found
        """
        return self.agents.get(agent_id)

    def delete_agent(self, agent_id: str) -> None:
        """
        Delete an agent.

        Args:
            agent_id: The agent identifier to delete
        """
        try:
            if agent_id in self.agents:
                agent_config = self.agents[agent_id]

                if agent_config.get("is_azure_agent") and self.project_client:
                    try:
                        with self.project_client:
                            self.project_client.agents.delete_agent(agent_id)
                            logger.info("Deleted Azure AI agent: %s", agent_id)
                    except Exception as e:
                        logger.error("Error deleting Azure agent: %s", e)

                del self.agents[agent_id]
                logger.info("Deleted agent from local storage: %s", agent_id)
        except Exception as e:
            logger.error("Error deleting agent %s: %s", agent_id, e)
