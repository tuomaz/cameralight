# Project Overview

This project is a Python application that fetches images from a list of URIs, calculates the average brightness of the images, and publishes the result to an MQTT topic. It also stores the history of the average brightness values in a SQLite database and sends a delayed value to another MQTT topic.

The application is configured using a `config.yaml` file and can be partially configured using environment variables.

## Building and Running

### Docker

The project includes a `Dockerfile` to build and run the application in a container.

**Build the image:**

```bash
docker build -t cameralight .
```

**Run the container:**

```bash
docker run -d --name cameralight \
  -v ./config.yaml:/app/config.yaml \
  -e MQTT_HOST=your_mqtt_host \
  -e MQTT_PORT=your_mqtt_port \
  cameralight
```

### Local Development

**Prerequisites:**

*   Python 3.9+
*   [Poetry](https://python-poetry.org/)

**Installation:**

```bash
poetry install
```

**Running the application:**

```bash
poetry run python main.py
```

A `config.yaml` file is required in the same directory.

## Development Conventions

*   **Dependency Management:** Uses Poetry.
*   **Configuration:** Managed via Pydantic (`settings.py`).
*   **Linting/Formatting:** Uses Ruff (`poetry run ruff check .`, `poetry run ruff format .`).
*   **Database:** SQLite interactions are encapsulated in `database.py`.
*   **Type Hinting:** Fully typed codebase.
