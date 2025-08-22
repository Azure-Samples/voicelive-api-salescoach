"""Tests for configuration management."""

import os
from unittest.mock import patch

from config import Config


class TestConfig:
    """Test configuration class."""

    def test_config_initialization(self):
        """Test that config initializes with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config["port"] == 8000
            assert config["host"] == "0.0.0.0"
            assert config["azure_ai_region"] == "swedencentral"

    def test_config_with_environment_variables(self):
        """Test that config loads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "PORT": "9000",
                "HOST": "localhost",
                "AZURE_AI_REGION": "westus",
                "AZURE_AI_RESOURCE_NAME": "test-resource",
            },
        ):
            config = Config()
            assert config["port"] == 9000
            assert config["host"] == "localhost"
            assert config["azure_ai_region"] == "westus"
            assert config["azure_ai_resource_name"] == "test-resource"

    def test_config_get_method(self):
        """Test the get method with defaults."""
        config = Config()
        assert config.get("nonexistent_key", "default") == "default"
        assert config.get("port", 0) == config["port"]

    def test_config_as_dict(self):
        """Test that as_dict returns a copy of the configuration."""
        config = Config()
        config_dict = config.as_dict
        assert isinstance(config_dict, dict)
        assert "port" in config_dict

        # Modify the returned dict - original should be unchanged
        config_dict["port"] = 9999
        assert config["port"] != 9999
        assert config["port"] != 9999
