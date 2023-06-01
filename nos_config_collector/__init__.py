"""Web service to collect, anonymize and save network device configuration files."""
import logging
import os
from importlib import resources
from importlib.resources import files
from io import StringIO
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from git import GitCommandError, InvalidGitRepositoryError
from git.repo import Repo
from git.util import Actor
from netconan.anonymize_files import FileAnonymizer  # type: ignore
from netutils.lib_mapper import NETMIKO_LIB_MAPPER
from pydantic import BaseModel, validator
from pydantic.env_settings import BaseSettings
from starlette import status
from starlette.responses import JSONResponse
from starlette.templating import _TemplateResponse


class Settings(BaseSettings):
    """Settings for ncc."""

    ncc_config_directory: Path
    ncc_repository_url: str
    ncc_repository_owner: str
    ncc_repository_name: str
    ncc_github_token: str
    ncc_github_timeout: int = 15
    ncc_base_branch: str = "main"
    ncc_log_level: int = logging.WARNING


class BaseSchema(BaseModel):
    """Base schema for all endpoints."""

    class Config:
        """Forbid extra fields, causing 422 if any such fields are posted."""

        extra = "forbid"
        abstract = True


class ConfigurationToStore(BaseSchema):
    """Configuration to be stored in git."""

    content: str
    author: str | None
    email: str | None
    nos: str


class StoredConfigurationResponse(BaseSchema):
    """Response schema for a configuration storage."""

    pr_link: str | None
    error: str | None


class ConfigurationToAnonymize(BaseSchema):
    """Return schema for anonymized configurations."""

    @validator("sensitive_words")
    def no_empty_sensitive_words(cls, value: list[str]) -> list[str]:
        """Remove any empty strings from 'sensitive_words'."""
        return [item for item in value if item.strip()]

    content: str
    sensitive_words: list[str] = []


class AnonymizedConfiguration(BaseSchema):
    """Configuration to be anonymized."""

    content: str


# Apply settings from file if present
config_file = Path(str(files("nos_config_collector"))).parent / "config.env"
if config_file.is_file() and os.environ.get("NCC_DEVELOPMENT", False):
    settings = Settings(_env_file=str(config_file), _env_file_encoding="utf-8")  # type: ignore
else:
    settings = Settings()

logging.basicConfig(level=settings.ncc_log_level)

app = FastAPI()
static_directory = resources.files("nos_config_collector") / "static"
app.mount("/static", StaticFiles(directory=str(static_directory)), name="static")
templates = Jinja2Templates(directory="nos_config_collector/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> _TemplateResponse:
    """Index page that shows the form for configuration submitting."""
    nos_list = list(NETMIKO_LIB_MAPPER.keys())
    nos_list.append("other")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "nos_list": sorted(nos_list),
        },
    )


@app.post("/configurations/anonymize/")
async def anonymize_config(configuration: ConfigurationToAnonymize) -> AnonymizedConfiguration:
    """
    Return the same config anonymized through netconan.

    Depends on this: https://github.com/intentionet/netconan/pull/186
    """
    # Empty sensitive words list causes netconan to freak out a little
    if not configuration.sensitive_words:
        configuration.sensitive_words = ["verylongstringthathopefullydoesn'tappearintheconfig"]
    anonymized_configuration = StringIO()
    anonymizer = FileAnonymizer(
        anon_ip=True,
        anon_pwd=True,
        salt="ncc",
        sensitive_words=configuration.sensitive_words,
    )
    anonymizer.anonymize_io(StringIO(configuration.content), anonymized_configuration)
    return AnonymizedConfiguration(content=anonymized_configuration.getvalue())


@app.post("/configurations/")
async def post_config(configuration: ConfigurationToStore) -> JSONResponse:
    """Post configurations."""
    try:
        settings.ncc_config_directory.mkdir(parents=True, exist_ok=True)
        repository = Repo(settings.ncc_config_directory)
    except InvalidGitRepositoryError:
        repository_url = settings.ncc_repository_url
        separator = "://"
        if separator in str(settings.ncc_repository_url):
            schema, url = str(settings.ncc_repository_url).split(separator)
            schema += separator
            repository_url = f"{schema}{settings.ncc_github_token}@{url}"
        repository = Repo.clone_from(url=repository_url, to_path=settings.ncc_config_directory)

    # Write configuration to the repository
    file_name = str(abs(hash(configuration.content)))  # We convert the hash to a positive number
    file_path = settings.ncc_config_directory / "configurations" / configuration.nos / f"{file_name}.conf"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, encoding="utf-8", mode="w") as f:
        f.write(configuration.content)

    # Create commit with local changes
    branch_name = f"add/{file_name}"
    try:
        repository.git.checkout("-b", branch_name, settings.ncc_base_branch)
    except GitCommandError as error:
        logging.debug(f"Error when trying to create new branch for configuration: {error}.")
        return JSONResponse(
            content={"error": "This configuration is already present in the collection.", "pr_link": None},
            status_code=status.HTTP_409_CONFLICT,
        )

    repository.index.add(str(file_path))
    actor = Actor(name=configuration.author, email=configuration.email)
    repository.index.commit(message=f"add: added configuration with hash {file_name}", author=actor)

    # Push branch to the upstream
    repository.git.push("--set-upstream", "origin", branch_name)

    # Create a PR on GitHub
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.ncc_github_token}",
    }
    payload = {
        "title": "Add new configuration file submitted through the network-device-config-collector",
        "head": f"{settings.ncc_repository_owner}:{branch_name}",
        "base": settings.ncc_base_branch,
        "body": "Pull Request submitted through the network-device-config-collector.",
    }
    response = requests.post(
        f"https://api.github.com/repos/{settings.ncc_repository_owner}/{settings.ncc_repository_name}/pulls",
        headers=headers,
        json=payload,
        timeout=settings.ncc_github_timeout,
    )

    pr_link = None
    error_message = None

    if response.ok:
        pr_link = response.json()["html_url"]
    else:
        error_message = response.text

    return JSONResponse(content={"pr_link": pr_link, "error": error_message}, status_code=status.HTTP_200_OK)
