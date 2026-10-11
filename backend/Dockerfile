# Build context is the repository root: the image serves the API and the built web app on one origin.
FROM node:24.18.0-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.14.7-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CC_WEB_DIR=/app/web
# Amazon RDS CA bundle for CC_DATABASE_URL=...?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem
ADD --chmod=644 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY --from=web /web/dist ./web
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]
CMD ["python", "-m", "app"]
