"""Web service to collect, anonymize and save network device configuration files."""
from pathlib import Path
from importlib import resources

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
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
static_directory = resources.files("nos_config_collector") / "static"
app.mount("/static", StaticFiles(directory=static_directory), name="static")
templates = Jinja2Templates(directory="nos_config_collector/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Index page that shows the form for configuration submitting."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/configurations/")
async def post_config(configuration: Configuration):
    """Post configurations."""
    try:
        repository = Repo(settings.ncc_config_directory)
    except InvalidGitRepositoryError:
        repository = Repo.clone_from(url=settings.ncc_repository_url, to_path=settings.ncc_config_directory)

    # Write configuration to the repository
    file_name = str(abs(hash(configuration.content)))  # We convert the hash to a positive number
    file_path = settings.ncc_config_directory / f"{file_name}.conf"
    with open(file_path, encoding="utf-8", mode="w") as f:
        f.write(configuration.content)

    # Create commit with local changes
    branch_name = f"add/{file_name}"
    repository.git.checkout("-b", branch_name)
    repository.index.add(str(file_path))
    actor = Actor(name=configuration.author, email=configuration.email)
    repository.index.commit(message=f"add: added configuration with hash {file_name}", author=actor)

    # Push branch to the upstream
    repository.git.push("--set-upstream", "origin", branch_name)
