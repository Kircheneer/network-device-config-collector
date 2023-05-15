"""Web service to collect, anonymize and save network device configuration files."""
from pathlib import Path

from fastapi import FastAPI
from git import InvalidGitRepositoryError, Repo
from git.util import Actor
from pydantic import BaseModel
from pydantic.env_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for ncc."""

    ncc_config_directory: Path = Path()
    ncc_repository_url: Path = Path()


class Configuration(BaseModel):
    """Store data for configuration POSTing."""

    content: str
    author: str | None
    email: str | None

    class Config:
        """Forbid extra fields, causing 422 if any such fields are posted."""

        extra = "forbid"


settings = Settings()
app = FastAPI()


@app.post("/configurations/")
async def post_config(configuration: Configuration):
    """Post configurations."""
    try:
        repository = Repo(settings.ncc_config_directory)
    except InvalidGitRepositoryError:
        repository = Repo.clone_from(url=settings.ncc_repository_url, to_path=settings.ncc_config_directory)

    file_name = str(hash(configuration.content))
    file_path = settings.ncc_config_directory / f"{file_name}.conf"
    with open(file_path, encoding="utf-8", mode="w") as f:
        f.write(configuration.content)

    repository.create_head(file_name).checkout()
    repository.index.add(str(file_path))
    actor = Actor(name=configuration.author, email=configuration.email)
    repository.index.commit(message=f"add: added configuration with hash {file_name}", author=actor)
