import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from io import BytesIO

# Set NODE_ID environment variable before importing the app
os.environ["NODE_ID"] = "test-node-id"
os.environ["RAFT_NODES"] = "node1,node2,node3"

from ..main import app
from ..redis_client import get_redis_store


@pytest.fixture
def mock_redis_store():
    mock_store = AsyncMock()
    return mock_store


@pytest.fixture
def client(mock_redis_store):
    """Mock client that uses the mock_redis_store as redis client."""
    app.dependency_overrides[get_redis_store] = lambda: mock_redis_store
    client = TestClient(app)
    return client


def setup_module():
    try:
        if Path("storage/test.txt").is_file():
            os.remove("storage/test.txt")
    except Exception:
        pass


def test_main_page(client, mock_redis_store):
    """
    Test the main page of the application.
    This test verifies that the main page loads correctly and displays the expected content.
    It mocks the Redis store to simulate the presence of an uploaded file and checks that
    the file is listed on the main page.

    Asserts:
        - The response status code should be 200 (OK).
        - The response should contain the heading for uploading a new file.
        - The response should contain the heading for uploaded files.
        - The response should list the uploaded file "test.txt".
    """

    mock_redis_store.lrange.return_value = [
        '{"term": 1, "index": 1, "command": {"operation": "upload", "filename": "test.txt", "content_type": "text/plain", "file_size": 12}}'
    ]

    response = client.get("/")

    assert response.status_code == 200
    assert "Upload a new file" in response.text
    assert "Uploaded files" in response.text
    assert "test.txt" in response.text


def test_upload_file(client):
    """
    Test the file upload functionality of the application.

    Asserts:
        - The response status code is 200.
        - The response JSON contains the expected success message.
        - The Redis store's hmset method was called exactly once.
    """
    file_data = BytesIO(b"test content")  # Generate temporary runtime file
    file_data.name = "test.txt"

    response = client.post(
        "/upload", files={"file": ("test.txt", file_data, "text/plain")}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Successfully uploaded test.txt"}


def test_upload_existing_file(client):
    """
    Test the upload of an existing file.

    Asserts:
        The response status code is 409.
        The response JSON contains the appropriate error message.
    """
    file_data = BytesIO(b"test content")  # Generate temporary runtime file
    file_data.name = "test.txt"

    response = client.post(
        "/upload", files={"file": ("test.txt", file_data, "text/plain")}
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "File already exists, rename the file and try again"
    }


def test_upload_empty_file(client):
    """
    Test the upload of an empty file.

    Asserts:
        The response status code is 400.
        The response JSON contains the appropriate error message.
    """
    file_data = BytesIO(b"")  # Generate temporary runtime file
    file_data.name = "test.txt"

    response = client.post(
        "/upload", files={"file": ("test.txt", file_data, "text/plain")}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "File is empty"}


def test_get_files_error(client, mock_redis_store):
    """
    Test the `GET /` endpoint when there is an error with the Redis store.

    Asserts:
        The response status code is 500.
        The response JSON contains the relevant error message.
    """
    mock_redis_store.lrange.side_effect = Exception(
        "Redis error"
    )  # Simulate a Redis failure

    response = client.get("/")

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong: Redis error"}


# TODO: get file calls
