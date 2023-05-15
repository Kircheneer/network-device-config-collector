from starlette import status


def test_frontend(test_client):
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
