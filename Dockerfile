# Registry digests verified 14 October 2026; application dependencies use locks.
FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS web
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY web ./web
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src SHORTLIST_MODE=hosted
WORKDIR /app
COPY requirements.runtime.txt ./
RUN pip install --no-cache-dir -r requirements.runtime.txt && useradd --uid 10001 --create-home shortlist
COPY src ./src
COPY migrations ./migrations
COPY scripts/migrate_postgres.py ./scripts/migrate_postgres.py
COPY --from=web /build/dist ./dist
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=8s --start-period=15s --retries=3 CMD ["python", "-m", "shortlist.container_health", "api"]
ENTRYPOINT ["python", "-m", "shortlist.container_entrypoint"]
CMD ["api"]
