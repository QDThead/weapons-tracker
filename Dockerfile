# PSI Control Tower — Defence Supply Chain Intelligence Platform
# Optimized for Azure Canada (Central/East) deployment
# PBMM-compliant container: no external network calls at build time

FROM python:3.11-slim AS base

# Security: non-root user
RUN groupadd -r psi && useradd -r -g psi -d /app -s /sbin/nologin psi

WORKDIR /app

# Install system dependencies for geospatial + PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fpdf2 jinja2

# Copy application
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/

# Create data directory for SQLite (persistent volume mount point)
RUN mkdir -p /app/data && chown -R psi:psi /app

# Switch to non-root
USER psi

# Environment
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///data/weapons_tracker.db
ENV PSI_ENVIRONMENT=production
ENV PSI_DATA_SOVEREIGNTY=canada
ENV PSI_AZURE_REGION=canadacentral

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Expose API port
EXPOSE 8000

# Seed database on first run, then start server
CMD ["sh", "-c", "python -m scripts.seed_database && python -m src.main"]
