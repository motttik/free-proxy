# Free Proxy - Multi-stage Dockerfile
# Produces a minimal distroless image for production

# ==============================================================================
# BUILD STAGE
# ==============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==============================================================================
# PRODUCTION STAGE
# ==============================================================================
FROM python:3.11-slim as production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY fp/ ./fp/

# Add scripts to PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from fp import FreeProxy; print('OK')" || exit 1

# Default command
ENTRYPOINT ["fp"]
CMD ["--help"]

# ==============================================================================
# DEVELOPMENT STAGE
# ==============================================================================
FROM production as development

USER root

# Install dev dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --user -r requirements-dev.txt

# Copy tests
COPY tests/ ./tests/

# Install in editable mode
COPY setup.py pyproject.toml ./
RUN pip install --no-cache-dir --user -e .

USER appuser

# Default command for development
CMD ["pytest", "-v"]
