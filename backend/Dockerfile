FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

EXPOSE 8000

# Run migrations, then start the API.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host ${API_HOST:-127.0.0.1} --port 8000"]
