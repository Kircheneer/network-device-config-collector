import pytest
from starlette.testclient import TestClient

from nos_config_collector import app


@pytest.fixture
def test_client():
    """Provide an API test client."""
    return TestClient(app)
