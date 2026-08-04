FROM python:3.12-slim

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Allow CI to substitute requirements-ce.txt (strips torch/timesfm for CE builds)
ARG REQUIREMENTS_FILE=requirements.txt

# Upgrade pip before installing deps.
# python:3.12-slim ships with pip 25.0.1 which has several high CVEs
# (GHSA-4xh5-x5gv-qwph, GHSA-wf93-45jw-7689, GHSA-58qw-9mgm-455v, etc.).
# Fixed in pip 25.3. This single line resolves all of them.
RUN pip install --no-cache-dir --upgrade pip

# Python deps
COPY requirements.txt requirements-ce.txt ./
RUN pip install --no-cache-dir -r "${REQUIREMENTS_FILE}"

# Application code
COPY . .

# Non-root user for production safety
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
