FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY app.py ./

RUN uv sync --frozen --no-dev

RUN useradd -m appuser
USER appuser

EXPOSE 8080

CMD ["sh", "-c", ".venv/bin/uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
