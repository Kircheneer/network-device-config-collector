FROM python:3.10.6

WORKDIR /opt/ndcc

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --no-cache-dir --upgrade pip
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.5.0 python3 -
ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml poetry.lock README.md .
RUN poetry install --no-ansi --no-root --no-interaction

COPY nos_config_collector nos_config_collector

RUN poetry install --only-root

CMD ["poetry", "run", "uvicorn", "nos_config_collector:app", "--host", "0.0.0.0", "--port", "80"]