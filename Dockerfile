FROM python:3.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install Poetry
RUN pip install poetry

# Copy configuration files
COPY pyproject.toml poetry.lock ./

# Install dependencies globally (no venv)
RUN poetry install --no-root --only main

# Copy application code
COPY . .

CMD ["python", "main.py"]
