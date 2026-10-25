# Single-container demo image: Next.js + Django API + worker + SimuText simulator.
# Build from the repository root:  docker build -f deploy/Dockerfile -t ccp-demo .
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ENV API_ORIGIN=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY simulator/requirements.txt simulator/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r simulator/requirements.txt honcho==2.0.0
COPY backend/ backend/
COPY simulator/ simulator/
COPY --from=web /web/.next/standalone web/
COPY --from=web /web/.next/static web/.next/static
COPY --from=web /web/public web/public
COPY deploy/Procfile deploy/start.sh ./
RUN cd backend && DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && useradd --create-home --uid 1000 app && mkdir -p /data && chown -R app /app /data
USER app
ENV PORT=3000
EXPOSE 3000
CMD ["sh", "start.sh"]
