"""Test the frontend of network-device-config-collector."""
from starlette import status


def test_frontend(test_client):
    """Test that the index page returns a 200 status."""
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
