# Stage 1: build the web app
FROM node:22-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: run the API and serve the built web app
FROM python:3.12-slim
LABEL org.opencontainers.image.authors="Meraj Akhtar <meraj@aiplanet.com>"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg converts voice replies to OGG/Opus so WhatsApp shows them as voice notes
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY --from=web /src/frontend/dist /srv/frontend/dist

RUN useradd --create-home --uid 1000 billmitra \
    && mkdir -p /srv/backend/var \
    && chown -R billmitra /srv/backend/var
USER billmitra

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
