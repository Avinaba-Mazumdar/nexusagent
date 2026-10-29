# NexusAgent Backend

Autonomous Architecture Intelligence & Systems Design Engine built with FastAPI, LangGraph, and Neon PostgreSQL 18.

## Requirements

- Python >= 3.14
- [uv](https://github.com/astral-sh/uv) fast Python package installer and resolver

## Getting Started

### 1. Install Dependencies

```bash
uv sync
```

### 2. Run the Development Server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Or use the entrypoint:

```bash
uv run python -m app.main
```

The interactive API documentation is available at:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Run Tests and Linters

```bash
uv run pytest
uv run ruff check .
```
