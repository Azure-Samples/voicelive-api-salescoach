"""Configuration management for the upskilling agent application."""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration class."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables with defaults."""
        config = {
            "azure_ai_resource_name": os.getenv("AZURE_AI_RESOURCE_NAME", ""),
            "azure_ai_region": os.getenv("AZURE_AI_REGION", "swedencentral"),
            "azure_ai_project_name": os.getenv("AZURE_AI_PROJECT_NAME", ""),
            "project_endpoint": os.getenv("PROJECT_ENDPOINT", ""),
            "use_azure_ai_agents": os.getenv("USE_AZURE_AI_AGENTS", "false").lower()
            == "true",
            "agent_id": os.getenv("AGENT_ID", ""),
            "port": int(os.getenv("PORT", "8000")),
            "host": os.getenv("HOST", "0.0.0.0"),
            "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
            "model_deployment_name": os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
            "subscription_id": os.getenv("SUBSCRIPTION_ID", ""),
            "resource_group_name": os.getenv("RESOURCE_GROUP_NAME", ""),
            "azure_speech_key": os.getenv("AZURE_SPEECH_KEY", ""),
            "azure_speech_region": os.getenv("AZURE_SPEECH_REGION", "swedencentral"),
        }
        return config

    def __getitem__(self, key: str) -> Any:
        """Get configuration value by key."""
        return self._config.get(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default."""
        return self._config.get(key, default)

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()


config = Config()
