FROM python:3.11-slim

WORKDIR /app

ARG UV_VERSION=0.11.31
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home app \
    && mkdir -p /app/data \
    && chown -R app:app /app

ENV PYTHONDONTWRITEBYTECODE=1
USER app

EXPOSE 8000

# Run migrations, then start the API.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host ${API_HOST:-127.0.0.1} --port 8000"]
