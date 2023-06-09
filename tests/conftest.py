"""Test configuration for network-device-config-collector."""
import logging
import os

import pytest
from starlette.testclient import TestClient

# Mocking settings
os.environ["ncc_config_directory"] = "/broken/dir"
os.environ["ncc_repository_url"] = "https://broken.url"
os.environ["ncc_repository_owner"] = "test-owner"
os.environ["ncc_repository_name"] = "test-network-device-config-collection"
os.environ["ncc_github_token"] = "not-a-token"  # noqa: S105
os.environ["ncc_base_branch"] = "main"
os.environ["ncc_log_level"] = str(logging.DEBUG)
from nos_config_collector import app  # noqa: 402


@pytest.fixture
def test_client():
    """Provide an API test client."""
    return TestClient(app)
