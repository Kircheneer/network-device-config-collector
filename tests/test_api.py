"""API tests for nos-config-collector."""
import shutil
from pathlib import Path

import pytest
import requests_mock
from fastapi import status
from git import InvalidGitRepositoryError, Repo

from nos_config_collector import settings


@pytest.fixture
def repository_path(tmp_path):
    """Create a temporary directory and initialize an empty repository into it."""
    path = tmp_path / "clone_to"
    path.mkdir()
    settings.ncc_config_directory = path
    # Repo.init(path, initial_branch=settings.ncc_base_branch)
    yield path
    shutil.rmtree(path)


@pytest.fixture(autouse=True)
def source_repository(tmp_path):
    """Create an empty repository to clone from."""
    path = tmp_path / "clone_from"
    path.mkdir()
    settings.ncc_repository_url = path
    repository = Repo.init(path, initial_branch=settings.ncc_base_branch)
    repository.index.commit(message="initial commit")
    yield repository
    shutil.rmtree(path)


def post_configuration(test_client, json):
    """Post a configuration file."""
    return test_client.post("/configurations/", json=json)


def test_post_empty_config(repository_path, test_client):
    """Assert that posting an empty config works."""
    configuration = ""
    nos = "test-nos"
    response = post_configuration(test_client=test_client, json={"content": configuration, "nos": nos})

    base_assert_message = "Posting an empty config "

    assert response.status_code == status.HTTP_200_OK, base_assert_message + "led to a non-200 HTTP status code"

    directory_content = [item for item in repository_path.iterdir() if item.name != ".git"]
    assert len(directory_content) == 1, base_assert_message + "generated an amount != 1 of directory items"

    file = repository_path / "configurations" / nos / f"{abs(hash(configuration))}.conf"
    try:
        with open(file) as f:
            assert configuration == f.read(), base_assert_message + "generated a non-empty file"
    except FileNotFoundError:
        pytest.fail(base_assert_message + "generated a file with the wrong filename")


def test_post_non_empty_config(repository_path, test_client):
    """Assert that posting a simple, one-line config, works as expected."""
    configuration = "simple config"
    nos = "test-nos"
    response = post_configuration(test_client=test_client, json={"content": configuration, "nos": nos})

    base_assert_message = "Posting a simple config "
    assert response.status_code == status.HTTP_200_OK, base_assert_message + "led to a non-200 HTTP status code"
    with open(repository_path / "configurations" / nos / f"{abs(hash(configuration))}.conf") as f:
        assert configuration == f.read(), base_assert_message + "did not write that config to the file"


def test_post_config_folder_is_git_repository(repository_path, test_client):
    """Assert that the configuration folder is a git repository."""
    post_configuration(test_client=test_client, json={"content": "", "nos": "test-nos"})
    try:
        Repo(repository_path)
    except InvalidGitRepositoryError:
        pytest.fail("Git repository wasn't created by posting configuration")


def test_post_config_clean_working_tree(repository_path, test_client):
    """Assert that the working tree is clean after posting a configuration."""
    post_configuration(test_client=test_client, json={"content": "", "nos": "test-nos"})
    repository = Repo(repository_path)
    assert not repository.is_dirty(), "Working tree is not clean after posting a configuration"


def test_post_config_git_metadata(repository_path, test_client):
    """Assert that git metadata is passed along correctly."""
    author = "Jane Doe"
    email = "jane@doe.example"
    configuration = ""
    post_configuration(
        test_client=test_client,
        json={"content": configuration, "author": author, "email": email, "nos": "test-nos"},
    )
    repository = Repo(repository_path)
    assert repository.head.commit.author.name == author
    assert repository.head.commit.author.email == email
    assert repository.head.commit.message == f"add: added configuration with hash {abs(hash(configuration))}"


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
    nos = "test-nos"
    configurations_dir_source = Path(source_repository.working_tree_dir) / "configurations" / nos
    configurations_dir_source.mkdir(exist_ok=True, parents=True)
    with open(configurations_dir_source / filename, "w") as f:
        f.write("existing config")
    source_repository.index.add(f"configurations/{nos}/{filename}")
    source_repository.index.commit(message="")

    configuration = ""
    post_configuration(test_client=test_client, json={"content": configuration, "nos": nos})

    configurations_dir_target = repository_path / "configurations" / nos
    expected_amount_of_configurations = 2
    assert (
        len(list(configurations_dir_target.glob("*.conf"))) == expected_amount_of_configurations
    ), "Existing configurations were not pulled"


def test_post_config_changes_pushed(repository_path, test_client, source_repository):
    """Assert that the posted changes are committed to a branch."""
    configuration = ""
    post_configuration(test_client=test_client, json={"content": configuration, "nos": "test-nos"})

    positive_config_hash = str(abs(hash(configuration)))
    branch_name = f"add/{positive_config_hash}"

    assert branch_name in [
        branch.name for branch in source_repository.branches
    ], "Branch wasn't pushed to remote repository"


def test_post_config_twice(repository_path, test_client):
    """Assert that two configurations may be posted."""
    configurations = ["first config", "second config"]
    for configuration in configurations:
        post_configuration(test_client=test_client, json={"content": configuration, "nos": "test-nos"})

    repository = Repo(repository_path)
    amount_of_branches = 3  # main plus one per config
    assert len(repository.branches) == amount_of_branches


def test_post_config_github_upload(repository_path, test_client):
    """Test that a POST request to the GitHub API would be performed."""
    configuration = "test config"
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.post(
            f"https://api.github.com/repos/{settings.ncc_repository_owner}/{settings.ncc_repository_name}/pulls",
            json={"html_url": "https://not.a.real.url"},
        )
        post_configuration(test_client=test_client, json={"content": configuration, "nos": "test-nos"})

    assert requests_mocker.last_request is not None


def test_post_anonymize(test_client):
    """Test that anonymizing an empty config returns an empty config."""
    configuration = ""
    response = test_client.post("/configurations/anonymize/", json={"content": configuration})
    response.raise_for_status()
    anonymized_configuration = response.json()
    assert anonymized_configuration["content"] == configuration


def test_post_anonymize_one_line(test_client):
    """Test that anonymizing a single, non-sensitive configuration line retains that line as-is."""
    input_configuration = "hostname test-device"
    response = test_client.post("/configurations/anonymize/", json={"content": input_configuration})
    response.raise_for_status()
    anonymized_configuration = response.json()
    assert (
        anonymized_configuration["content"] == input_configuration
    ), "Unsensitive configuration not preserved properly during anonymization"


def test_post_anonymization(test_client, mocker):
    """Test that anonymization of a password works."""
    password = "mypassword"  # noqa: S105

    # Mock netconan implementation
    class FakeFileAnonymizer:
        def _mocked_anonymize_configuration(self, io_in, io_out):
            for line in io_in:
                io_out.write(line.replace(password, "$censored"))

    mocker.patch("netconan.anonymize_files.FileAnonymizer", FakeFileAnonymizer)
    input_configuration = f"password {password}"

    response = test_client.post("/configurations/anonymize/", json={"content": input_configuration})
    response.raise_for_status()
    anonymized_configuration = response.json()
    assert (
        password not in anonymized_configuration["content"]
    ), "Password was not anonymized properly, is netconan being used?"


def test_post_anonymization_sensitive_words(test_client):
    """Test that sensitive words can be passed to the anonymizer."""
    input_configuration = "sensitive"
    response = test_client.post(
        "/configurations/anonymize/", json={"content": input_configuration, "sensitive_words": ["sensitive"]}
    )
    response.raise_for_status()
    anonymized_configuration = response.json()
    assert (
        "sensitive" not in anonymized_configuration["content"]
    ), "Sensitive words functionality for config anonymization not working"
