"""Business logic managers for the upskilling agent application."""

import logging
import uuid
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

from azure.identity import DefaultAzureCredential

from config import config

# Conditionally import Azure AI Projects SDK
try:
    from azure.ai.projects import AIProjectClient

    AZURE_AI_AGENTS_AVAILABLE = True
except ImportError:
    AZURE_AI_AGENTS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "Azure AI Projects SDK not available - using instruction-based approach only"
    )

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages Azure authentication tokens with automatic refresh."""

    def __init__(self):
        """Initialize the token manager."""
        self.credential = None
        self.token = None
        self.expires_at = None

    def get_token(self) -> str:
        """
        Get a valid authentication token, refreshing if necessary.

        Returns:
            str: Valid authentication token
        """
        if not self.token or datetime.now() >= (self.expires_at - timedelta(minutes=5)):
            self.credential = self.credential or DefaultAzureCredential()
            token_response = self.credential.get_token("https://ai.azure.com/.default")
            self.token = token_response.token
            self.expires_at = datetime.fromtimestamp(token_response.expires_on)
            logger.info(f"Token refreshed, expires at {self.expires_at}")
        return self.token


class ScenarioManager:
    """Manages training scenarios loaded from YAML files."""

    def __init__(self, scenario_dir: Path = None):
        """
        Initialize the scenario manager.

        Args:
            scenario_dir: Directory containing scenario YAML files
        """
        if scenario_dir is None:
            docker_path = Path("/app/data/scenarios")
            if docker_path.exists():
                self.scenario_dir = docker_path
            else:
                self.scenario_dir = (
                    Path(__file__).parent.parent.parent.parent / "data" / "scenarios"
                )
        else:
            self.scenario_dir = scenario_dir

        self.scenarios = self._load_scenarios()

    def _load_scenarios(self) -> Dict[str, Any]:
        """
        Load scenarios from YAML files.

        Returns:
            Dict[str, Any]: Dictionary of scenarios keyed by ID
        """
        scenarios = {}

        if not self.scenario_dir.exists():
            logger.warning(f"Scenarios directory not found: {self.scenario_dir}")
            return scenarios

        for file in self.scenario_dir.glob("*role-play.prompt.yml"):
            try:
                with open(file) as f:
                    scenario = yaml.safe_load(f)
                    scenario_id = file.stem.replace("-role-play.prompt", "")
                    scenarios[scenario_id] = scenario
                    logger.info(f"Loaded scenario: {scenario_id}")
            except Exception as e:
                logger.error(f"Error loading scenario {file}: {e}")

        logger.info(f"Total scenarios loaded: {len(scenarios)}")
        return scenarios

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific scenario by ID.

        Args:
            scenario_id: The scenario identifier

        Returns:
            Optional[Dict[str, Any]]: Scenario data or None if not found
        """
        return self.scenarios.get(scenario_id)

    def list_scenarios(self) -> List[Dict[str, str]]:
        """
        List all available scenarios.

        Returns:
            List[Dict[str, str]]: List of scenario summaries
        """
        return [
            {
                "id": scenario_id,
                "name": scenario_data.get("name", "Unknown"),
                "description": scenario_data.get("description", ""),
            }
            for scenario_id, scenario_data in self.scenarios.items()
        ]


class AgentManager:
    """Manages virtual training agents."""

    # Base instructions for human-like interactions
    BASE_INSTRUCTIONS = """

CRITICAL INTERACTION GUIDELINES:
- Keep responses SHORT and conversational (2-3 sentences max, as if speaking on phone)
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
        self.agents = {}
        self.credential = DefaultAzureCredential()
        self.use_azure_ai_agents = (
            config["use_azure_ai_agents"] and AZURE_AI_AGENTS_AVAILABLE
        )
        self.project_client = None

        if self.use_azure_ai_agents:
            self.project_client = self._initialize_project_client()
            logger.info("AgentManager initialized with Azure AI Agent Service support")
        else:
            logger.info("AgentManager initialized with instruction-based approach only")

    def _initialize_project_client(self) -> Optional["AIProjectClient"]:
        """Initialize the Azure AI Project client."""
        if not AZURE_AI_AGENTS_AVAILABLE:
            return None

        try:
            project_endpoint = config["project_endpoint"]
            if not project_endpoint:
                logger.warning(
                    "PROJECT_ENDPOINT not configured - falling back to instruction-based approach"
                )
                return None

            client = AIProjectClient(
                endpoint=project_endpoint,
                credential=self.credential,
            )
            logger.info(
                f"AI Project client initialized with endpoint: {project_endpoint}"
            )
            return client
        except Exception as e:
            logger.error(f"Failed to initialize AI Project client: {e}")
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
        # Combine base instructions with scenario-specific instructions
        scenario_instructions = scenario_data.get("messages", [{}])[0].get(
            "content", ""
        )
        combined_instructions = scenario_instructions + self.BASE_INSTRUCTIONS

        # Get model configuration
        model_name = scenario_data.get("model", config["model_deployment_name"])
        temperature = scenario_data.get("modelParameters", {}).get("temperature", 0.7)
        max_tokens = scenario_data.get("modelParameters", {}).get("max_tokens", 2000)

        if self.use_azure_ai_agents and self.project_client:
            # New approach: Create agent in Azure AI Foundry
            return self._create_azure_agent(
                scenario_id, combined_instructions, model_name, temperature, max_tokens
            )
        else:
            # Old approach: Create local agent configuration only
            return self._create_local_agent(
                scenario_id, combined_instructions, model_name, temperature, max_tokens
            )

    def _create_azure_agent(
        self,
        scenario_id: str,
        instructions: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Create an agent using Azure AI Agent Service."""
        try:
            with self.project_client:
                agent = self.project_client.agents.create_agent(
                    model=model,
                    name=f"agent-{scenario_id}-{uuid.uuid4().hex[:8]}",
                    instructions=instructions,
                    tools=[],  # Add tools if needed
                    temperature=temperature,
                )

                agent_id = agent.id
                logger.info(f"Created Azure AI agent: {agent_id}")

                # Store agent configuration locally for reference
                self.agents[agent_id] = {
                    "scenario_id": scenario_id,
                    "azure_agent_id": agent_id,
                    "is_azure_agent": True,  # Mark as Azure-created agent
                    "instructions": instructions,
                    "created_at": datetime.now(),
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                return agent_id

        except Exception as e:
            logger.error(f"Error creating Azure agent: {e}")
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
            # Generate a unique agent ID
            agent_id = f"local-agent-{scenario_id}-{uuid.uuid4().hex[:8]}"

            # Store agent configuration locally
            self.agents[agent_id] = {
                "scenario_id": scenario_id,
                "is_azure_agent": False,  # Mark as local-only agent
                "instructions": instructions,
                "created_at": datetime.now(),
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            logger.info(f"Created local agent configuration: {agent_id}")
            return agent_id

        except Exception as e:
            logger.error(f"Error creating local agent: {e}")
            raise

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

                # Only delete from Azure if it's an Azure-created agent
                if agent_config.get("is_azure_agent") and self.project_client:
                    try:
                        with self.project_client:
                            self.project_client.agents.delete_agent(agent_id)
                            logger.info(f"Deleted Azure AI agent: {agent_id}")
                    except Exception as e:
                        logger.error(f"Error deleting Azure agent: {e}")

                # Remove from local storage
                del self.agents[agent_id]
                logger.info(f"Deleted agent from local storage: {agent_id}")
        except Exception as e:
            logger.error(f"Error deleting agent {agent_id}: {e}")
