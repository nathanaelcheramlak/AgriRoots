FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libespeak-ng1 && rm -rf /var/lib/apt/lists/*
COPY requirements-connectors.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-connectors.lock
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts/sync_verified_skills.py ./scripts/sync_verified_skills.py
COPY reports/provider_inventory.json ./reports/provider_inventory.json
RUN useradd --uid 10001 --create-home agrilo && mkdir -p /app/private-data && chown -R agrilo:agrilo /app/private-data
USER agrilo
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
