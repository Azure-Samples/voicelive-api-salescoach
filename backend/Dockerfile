FROM node:20-alpine AS frontend-builder

WORKDIR /app

RUN npm config set strict-ssl false

COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps --include=dev

COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
COPY frontend/index.html ./
COPY frontend/vite.config.ts ./
COPY frontend/tsconfig.json ./
COPY frontend/tsconfig.node.json ./
COPY frontend/eslint.config.js ./
COPY frontend/.prettierrc ./
COPY frontend/.prettierignore ./

RUN npx --yes tsc && npx --yes vite build

# Stage 2: Python runtime (using Ubuntu 20.04 base to avoid OpenSSL 3 issues with speechsdk)
FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=src/app.py \
    FLASK_ENV=production \
    PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org" \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ca-certificates \
    libasound2 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY --chown=app:app backend/src/ ./src/
COPY --chown=app:app data/scenarios/ ./data/scenarios/
COPY --chown=app:app data/graph-api-canned.json ./data/

COPY --from=frontend-builder --chown=app:app /app/static/ ./static/

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/config || exit 1

CMD ["python", "src/app.py"]