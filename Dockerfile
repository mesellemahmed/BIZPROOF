FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY examples ./examples
COPY contracts ./contracts

RUN pip install --no-cache-dir -e ".[dev]"

ENTRYPOINT ["bizproof"]
