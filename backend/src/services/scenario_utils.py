"""Utility functions for scenario management."""

from pathlib import Path
from typing import Optional

# Constants
SCENARIO_DATA_DIR = "data/scenarios"
DOCKER_APP_PATH = "/app"


def determine_scenario_directory(scenario_dir: Optional[Path] = None) -> Path:
    """
    Determine the correct scenario directory path.

    Args:
        scenario_dir: Optional custom directory path

    Returns:
        Path: The resolved scenario directory path
    """
    if scenario_dir is not None:
        return scenario_dir

    docker_path = Path(DOCKER_APP_PATH) / SCENARIO_DATA_DIR
    if docker_path.exists():
        return docker_path

    return Path(__file__).parent.parent.parent.parent / "data" / "scenarios"
