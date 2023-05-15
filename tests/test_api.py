"""API tests for nos-config-collector."""
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from git import InvalidGitRepositoryError, Repo

from nos_config_collector import app, settings


@pytest.fixture
def test_client():
    """Provide an API test client."""
    return TestClient(app)


@pytest.fixture
def repository_path(tmpdir):
    """Create a temporary directory and initialize an empty repository into it."""
    path = Path(tmpdir.mkdir("clone_to"))
    settings.ncc_config_directory = path
    return path


@pytest.fixture(autouse=True)
def source_repository(tmpdir):
    """Create an empty repository to clone from."""
    path = tmpdir.mkdir("clone_from")
    settings.ncc_repository_url = path
    repository = Repo.init(path)
    repository.index.commit(message="initial commit")
    return repository


def post_configuration(test_client, json):
    """Post a configuration file."""
    return test_client.post("/configurations/", json=json)


def test_post_empty_config(repository_path, test_client):
    """Assert that posting an empty config works."""
    configuration = ""
    response = post_configuration(test_client=test_client, json={"content": configuration})

    base_assert_message = "Posting an empty config "

    assert response.status_code == status.HTTP_200_OK, base_assert_message + "led to a non-200 HTTP status code"

    directory_content = [item for item in repository_path.iterdir() if item.name != ".git"]
    assert len(directory_content) == 1, base_assert_message + "generated an amount != 1 of directory items"

    file = repository_path / f"{hash(configuration)}.conf"
    try:
        with open(file) as f:
            assert configuration == f.read(), base_assert_message + "generated a non-empty file"
    except FileNotFoundError:
        pytest.fail(base_assert_message + "generated a file with the wrong filename")


def test_post_non_empty_config(repository_path, test_client):
    """Assert that posting a simple, one-line config, works as expected."""
    configuration = "simple config"
    response = post_configuration(test_client=test_client, json={"content": configuration})

    base_assert_message = "Posting a simple config "
    assert response.status_code == status.HTTP_200_OK, base_assert_message + "led to a non-200 HTTP status code"
    with open(repository_path / f"{hash(configuration)}.conf") as f:
        assert configuration == f.read(), base_assert_message + "did not write that config to the file"


def test_post_config_folder_is_git_repository(repository_path, test_client):
    """Assert that the configuration folder is a git repository."""
    post_configuration(test_client=test_client, json={"content": ""})
    try:
        Repo(repository_path)
    except InvalidGitRepositoryError:
        pytest.fail("Git repository wasn't created by posting configuration")


def test_post_config_clean_working_tree(repository_path, test_client):
    """Assert that the working tree is clean after posting a configuration."""
    post_configuration(test_client=test_client, json={"content": ""})
    repository = Repo(repository_path)
    assert not repository.is_dirty(), "Working tree is not clean after posting a configuration"


def test_post_config_git_metadata(repository_path, test_client):
    """Assert that git metadata is passed along correctly."""
    author = "Jane Doe"
    email = "jane@doe.example"
    configuration = ""
    post_configuration(
        test_client=test_client,
        json={"content": configuration, "author": author, "email": email},
    )
    repository = Repo(repository_path)
    assert repository.head.commit.author.name == author
    assert repository.head.commit.author.email == email
    assert repository.head.commit.message == f"add: added configuration with hash {hash(configuration)}"


def test_post_config_no_content(repository_path, test_client):
    """Assert that the response code is 422 when empty JSON is posted."""
    response = post_configuration(test_client=test_client, json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_post_config_extra_content(repository_path, test_client):
    """Assert that the response code is 422 when JSON with extra fields is posted."""
    response = post_configuration(test_client=test_client, json={"content": "", "extra": "field"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_post_config_no_existing_repository(repository_path, test_client, source_repository):
    """Assert that given a non-cloned repository the repository is cloned."""
    filename = "existing_config.conf"
    with open(Path(source_repository.working_tree_dir) / filename, "w") as f:
        f.write("existing config")
    source_repository.index.add(filename)
    source_repository.index.commit(message="")

    configuration = ""
    post_configuration(test_client=test_client, json={"content": configuration})

    expected_amount_of_configurations = 2
    assert (
        len(list(repository_path.glob("*.conf"))) == expected_amount_of_configurations
    ), "Existing configurations were not pulled"


def test_post_config_changes_pushed(test_client, source_repository):
    """Assert that the posted changes are committed to a branch."""
    configuration = ""
    post_configuration(test_client=test_client, json={"content": configuration})

    assert str(hash(configuration)) in [
        branch.name for branch in source_repository.branches
    ], "Branch wasn't pushed to remote repository"
