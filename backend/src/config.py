# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------

"""Configuration management for the upskilling agent application."""

import os
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

# Default values as constants
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"
DEFAULT_REGION = "swedencentral"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_API_VERSION = "2024-12-01-preview"
DEFAULT_SPEECH_LANGUAGE = "en-US"
DEFAULT_INPUT_TRANSCRIPTION_MODEL = "azure-speech"
DEFAULT_INPUT_NOISE_REDUCTION_TYPE = "azure_deep_noise_suppression"
DEFAULT_VOICE_NAME = "en-US-Ava:DragonHDLatestNeural"
DEFAULT_VOICE_TYPE = "azure-standard"
DEFAULT_AVATAR_CHARACTER = "lisa"
DEFAULT_AVATAR_STYLE = "casual-sitting"


class Config:
    """Application configuration class."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables with defaults."""
        result: Dict[str, Any] = {
            "azure_ai_resource_name": os.getenv("AZURE_AI_RESOURCE_NAME", ""),
            "azure_ai_region": os.getenv("AZURE_AI_REGION", DEFAULT_REGION),
            "azure_ai_project_name": os.getenv("AZURE_AI_PROJECT_NAME", ""),
            "project_endpoint": os.getenv("PROJECT_ENDPOINT", ""),
            "use_azure_ai_agents": self._parse_bool_env("USE_AZURE_AI_AGENTS"),
            "agent_id": os.getenv("AGENT_ID", ""),
            "port": int(os.getenv("PORT", str(DEFAULT_PORT))),
            "host": os.getenv("HOST", DEFAULT_HOST),
            "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
            "model_deployment_name": os.getenv("MODEL_DEPLOYMENT_NAME", DEFAULT_MODEL),
            "subscription_id": os.getenv("SUBSCRIPTION_ID", ""),
            "resource_group_name": os.getenv("RESOURCE_GROUP_NAME", ""),
            "azure_speech_key": os.getenv("AZURE_SPEECH_KEY", ""),
            "azure_speech_region": os.getenv("AZURE_SPEECH_REGION", DEFAULT_REGION),
            "azure_speech_language": os.getenv("AZURE_SPEECH_LANGUAGE", DEFAULT_SPEECH_LANGUAGE),
            "api_version": DEFAULT_API_VERSION,
            # NEW ADDITIONS
            "azure_input_transcription_model": os.getenv(
                "AZURE_INPUT_TRANSCRIPTION_MODEL", DEFAULT_INPUT_TRANSCRIPTION_MODEL
            ),
            "azure_input_transcription_language": os.getenv(
                "AZURE_INPUT_TRANSCRIPTION_LANGUAGE", DEFAULT_SPEECH_LANGUAGE
            ),
            "azure_input_noise_reduction_type": os.getenv(
                "AZURE_INPUT_NOISE_REDUCTION_TYPE", DEFAULT_INPUT_NOISE_REDUCTION_TYPE
            ),
            "azure_voice_name": os.getenv("AZURE_VOICE_NAME", DEFAULT_VOICE_NAME),
            "azure_voice_type": os.getenv("AZURE_VOICE_TYPE", DEFAULT_VOICE_TYPE),
            "azure_avatar_character": os.getenv("AZURE_AVATAR_CHARACTER", DEFAULT_AVATAR_CHARACTER),
            "azure_avatar_style": os.getenv("AZURE_AVATAR_STYLE", DEFAULT_AVATAR_STYLE),
        }
        return result

    def _parse_bool_env(self, env_var: str, default: bool = False) -> bool:
        """Parse boolean environment variable."""
        return os.getenv(env_var, str(default)).lower() == "true"

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
