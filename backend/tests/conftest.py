"""Shared test configuration and fixtures for all test suites."""

import os
import pytest


def _load_azd_env():
    """Load Azure environment from azd .env file at module level.

    Must run at import time so pytest markers can evaluate skip conditions.
    """
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".azure", "newtest", ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"')
                    if key:
                        os.environ[key] = value

    # Prevent stale keys from root .env being loaded by load_dotenv().
    # Set to empty string (not pop) so load_dotenv doesn't override with stale values.
    root_env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(root_env):
        os.environ["AZURE_OPENAI_API_KEY"] = ""
        os.environ["AZURE_SPEECH_KEY"] = ""
        os.environ["AZURE_AI_PROJECT_KEY"] = ""


# Load at import time so markers work
_load_azd_env()


def _azure_env_available() -> bool:
    """Check if Azure environment variables are configured for integration/e2e tests."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        return False
    # Accept API key, client ID (managed identity), or just the endpoint
    # (DefaultAzureCredential will try various auth methods automatically)
    return True


def _speech_env_available() -> bool:
    """Check if Azure Speech environment variables are configured."""
    return bool(os.getenv("AZURE_SPEECH_REGION"))


# Markers for conditional skipping
requires_azure = pytest.mark.skipif(
    not _azure_env_available(),
    reason="AZURE_OPENAI_ENDPOINT and credentials not set",
)

requires_speech = pytest.mark.skipif(
    not _speech_env_available(),
    reason="AZURE_SPEECH_REGION and credentials not set",
)

requires_live_endpoint = pytest.mark.skipif(
    not os.getenv("SERVICE_VOICELAB_URI"),
    reason="SERVICE_VOICELAB_URI not set",
)


@pytest.fixture(scope="session")
def azure_env():
    """Provide Azure environment variables as a dict."""
    return {
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "speech_region": os.getenv("AZURE_SPEECH_REGION", ""),
        "resource_name": os.getenv("AI_FOUNDRY_RESOURCE_NAME", ""),
        "service_uri": os.getenv("SERVICE_VOICELAB_URI", ""),
    }
