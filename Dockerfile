FROM python:3.11-slim

WORKDIR /opt/ndcc

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_VERSION="1.5.0"

RUN pip install --no-cache-dir --upgrade pip
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python
ENV PATH="${PATH}:/root/.local/bin"
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-ansi --no-root --no-interaction --without dev

COPY nos_config_collector nos_config_collector

RUN poetry install --only-root

CMD ["poetry", "run", "uvicorn", "nos_config_collector:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]