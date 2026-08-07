# Use a stable slim image
FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install system packages needed for building/wrapping libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY app/requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app/ /app

# Create non-root user and fix permissions to match k8s runAsUser
RUN useradd -u 10001 -m -s /bin/false appuser \
    && chown -R appuser:appuser /app /tmp

USER appuser

# Expose the application port
EXPOSE 5000

# Use gunicorn for production; bind to 0.0.0.0:5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "2", "--timeout", "30"]
