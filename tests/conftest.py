"""Test configuration for network-device-config-collector."""
import os

import pytest
from starlette.testclient import TestClient

# Mocking settings
os.environ["ncc_config_directory"] = "/broken/dir"
os.environ["ncc_repository_url"] = "https://broken.url"
from nos_config_collector import app  # noqa: 402


@pytest.fixture
def test_client():
    """Provide an API test client."""
    return TestClient(app)
