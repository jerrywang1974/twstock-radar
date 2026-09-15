FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build context must be the parent directory that contains both:
#   twstock/          (library)
#   twstock-radar/    (this app)
COPY twstock /opt/twstock
COPY twstock-radar /app

# Install local twstock first, then radar app without resolving twstock from PyPI.
# twstock uses uv-dynamic-versioning (needs Git). Build context excludes .git via
# parent .dockerignore, so bypass VCS version detection for the image build.
ARG TWSTOCK_VERSION=0.0.0+docker
ENV UV_DYNAMIC_VERSIONING_BYPASS=${TWSTOCK_VERSION}
RUN pip install --no-cache-dir -e /opt/twstock \
    && pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.30.0" \
        "sqlalchemy>=2.0.0" \
        "alembic>=1.13.0" \
        "psycopg[binary]>=3.2.0" \
        "pydantic-settings>=2.0.0" \
        "apscheduler>=3.10.0" \
        "httpx>=0.27.0" \
        "python-dotenv>=1.0.0" \
        "openai>=1.40.0" \
    && pip install --no-cache-dir --no-deps -e /app

ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/radar.db \
    TIMEZONE=Asia/Taipei

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
