"""Tests for the managers module."""

import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import yaml

from managers import TokenManager, ScenarioManager, AgentManager


class TestTokenManager:
    """Test token manager functionality."""

    def test_token_manager_initialization(self):
        """Test that token manager initializes correctly."""
        manager = TokenManager()
        assert manager.credential is None
        assert manager.token is None
        assert manager.expires_at is None

    @patch("managers.DefaultAzureCredential")
    def test_get_token_first_time(self, mock_credential_class):
        """Test getting token for the first time."""
        # Mock the credential and token response
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        mock_token_response = Mock()
        mock_token_response.token = "test-token"
        mock_token_response.expires_on = (
            datetime.now() + timedelta(hours=1)
        ).timestamp()
        mock_credential.get_token.return_value = mock_token_response

        manager = TokenManager()
        token = manager.get_token()

        assert token == "test-token"
        assert manager.token == "test-token"
        assert manager.credential is not None

    @patch("managers.DefaultAzureCredential")
    def test_get_token_with_valid_existing_token(self, mock_credential_class):
        """Test getting token when valid token exists."""
        manager = TokenManager()
        manager.token = "existing-token"
        manager.expires_at = datetime.now() + timedelta(hours=1)

        token = manager.get_token()
        assert token == "existing-token"
        # Should not call credential methods
        mock_credential_class.assert_not_called()


class TestScenarioManager:
    """Test scenario manager functionality."""

    def test_scenario_manager_with_nonexistent_directory(self):
        """Test scenario manager with non-existent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = Path(temp_dir) / "nonexistent"
            manager = ScenarioManager(scenario_dir=non_existent_path)
            assert len(manager.scenarios) == 0

    def test_scenario_manager_with_valid_scenarios(self):
        """Test scenario manager loading valid scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            scenario_dir = Path(temp_dir)

            # Create a test scenario file
            scenario_data = {
                "name": "Test Scenario",
                "description": "A test scenario",
                "messages": [{"content": "Test instructions"}],
            }

            scenario_file = scenario_dir / "test-scenario-role-play.prompt.yml"
            with open(scenario_file, "w") as f:
                yaml.safe_dump(scenario_data, f)

            manager = ScenarioManager(scenario_dir=scenario_dir)
            assert len(manager.scenarios) == 1
            assert "test-scenario" in manager.scenarios

    def test_get_scenario_existing(self):
        """Test getting an existing scenario."""
        manager = ScenarioManager()
        manager.scenarios = {"test": {"name": "Test Scenario"}}

        scenario = manager.get_scenario("test")
        assert scenario is not None
        assert scenario["name"] == "Test Scenario"

    def test_get_scenario_nonexistent(self):
        """Test getting a non-existent scenario."""
        manager = ScenarioManager()
        manager.scenarios = {}

        scenario = manager.get_scenario("nonexistent")
        assert scenario is None

    def test_list_scenarios(self):
        """Test listing scenarios."""
        manager = ScenarioManager()
        manager.scenarios = {
            "scenario1": {"name": "Scenario 1", "description": "First scenario"},
            "scenario2": {"name": "Scenario 2", "description": "Second scenario"},
        }

        scenarios = manager.list_scenarios()
        assert len(scenarios) == 2
        assert scenarios[0]["id"] == "scenario1"
        assert scenarios[0]["name"] == "Scenario 1"


class TestAgentManager:
    """Test cases for AgentManager."""

    @patch("managers.config")
    def test_create_agent_success_local(self, mock_config):
        """Test successful local agent creation."""
        # Configure for local agent creation (no Azure AI Agents)
        mock_config.__getitem__.side_effect = lambda key: {
            "use_azure_ai_agents": False,
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        manager = AgentManager()
        scenario_data = {
            "messages": [{"content": "Test instructions"}],
            "model": "gpt-4",
            "modelParameters": {"temperature": 0.8, "max_tokens": 1500},
        }

        agent_id = manager.create_agent("test-scenario", scenario_data)

        assert agent_id.startswith("local-agent-test-scenario-")
        assert agent_id in manager.agents
        assert manager.agents[agent_id]["scenario_id"] == "test-scenario"
        assert manager.agents[agent_id]["is_azure_agent"] is False
        assert "Test instructions" in manager.agents[agent_id]["instructions"]
        assert manager.BASE_INSTRUCTIONS in manager.agents[agent_id]["instructions"]

    @patch("managers.AIProjectClient", create=True)
    @patch("managers.AZURE_AI_AGENTS_AVAILABLE", True)
    @patch("managers.config")
    def test_create_agent_success_azure(self, mock_config, mock_ai_client_class):
        """Test successful Azure agent creation."""
        # Configure for Azure agent creation
        mock_config.__getitem__.side_effect = lambda key: {
            "use_azure_ai_agents": True,
            "project_endpoint": "https://test.azure.com",
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        # Mock the AI client
        mock_ai_client = MagicMock()
        mock_ai_client_class.return_value = mock_ai_client

        # Mock the agent creation
        mock_agent = MagicMock()
        mock_agent.id = "asst_test123"
        mock_ai_client.__enter__.return_value = mock_ai_client
        mock_ai_client.agents.create_agent.return_value = mock_agent

        manager = AgentManager()
        scenario_data = {
            "messages": [{"content": "Test instructions"}],
            "model": "gpt-4",
            "modelParameters": {"temperature": 0.8, "max_tokens": 1500},
        }

        agent_id = manager.create_agent("test-scenario", scenario_data)

        assert agent_id == "asst_test123"
        assert agent_id in manager.agents
        assert manager.agents[agent_id]["scenario_id"] == "test-scenario"
        assert manager.agents[agent_id]["is_azure_agent"] is True

    def test_get_agent_existing(self):
        """Test getting an existing agent."""
        manager = AgentManager()
        test_agent = {"scenario_id": "test", "instructions": "Test"}
        manager.agents["test-agent"] = test_agent

        agent = manager.get_agent("test-agent")
        assert agent == test_agent

    def test_get_agent_nonexistent(self):
        """Test getting a non-existent agent."""
        manager = AgentManager()

        agent = manager.get_agent("nonexistent")
        assert agent is None

    def test_delete_agent_existing(self):
        """Test deleting an existing agent."""
        manager = AgentManager()
        manager.agents["test-agent"] = {"scenario_id": "test"}

        manager.delete_agent("test-agent")
        assert "test-agent" not in manager.agents

    def test_delete_agent_nonexistent(self):
        """Test deleting a non-existent agent (should not raise error)."""
        manager = AgentManager()

        # Should not raise an exception
        manager.delete_agent("nonexistent")
        assert len(manager.agents) == 0

    @patch("managers.config")
    def test_delete_agent_local(self, mock_config):
        """Test deleting a local agent."""
        mock_config.__getitem__.side_effect = lambda key: {
            "use_azure_ai_agents": False,
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        manager = AgentManager()
        manager.agents["test-agent"] = {"scenario_id": "test", "is_azure_agent": False}

        manager.delete_agent("test-agent")
        assert "test-agent" not in manager.agents

    @patch("managers.AIProjectClient", create=True)
    @patch("managers.AZURE_AI_AGENTS_AVAILABLE", True)
    @patch("managers.config")
    def test_delete_agent_azure(self, mock_config, mock_ai_client_class):
        """Test deleting an Azure agent."""
        mock_config.__getitem__.side_effect = lambda key: {
            "use_azure_ai_agents": True,
            "project_endpoint": "https://test.azure.com",
            "model_deployment_name": "gpt-4o",
        }.get(key, "default")

        # Mock the AI client
        mock_ai_client = MagicMock()
        mock_ai_client_class.return_value = mock_ai_client
        mock_ai_client.__enter__.return_value = mock_ai_client

        manager = AgentManager()
        manager.agents["test-agent"] = {"scenario_id": "test", "is_azure_agent": True}

        manager.delete_agent("test-agent")

        assert "test-agent" not in manager.agents
        mock_ai_client.agents.delete_agent.assert_called_once_with("test-agent")
