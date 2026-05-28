FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user
RUN groupadd -r gaoding && useradd -r -g gaoding -d /app -s /sbin/nologin gaoding

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for frontend build)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY requirements.txt requirements-test.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-test.txt

# Copy frontend package files
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./dashboard/frontend/

# Install frontend dependencies
RUN cd dashboard/frontend && npm ci

# Copy project files
COPY . .

# Build frontend
RUN cd dashboard/frontend && npm run build

# Create necessary directories
RUN mkdir -p /app/data/logs \
    /app/queue/actions/processed \
    /app/queue/status \
    /app/queue/review \
    /app/queue/pending \
    /app/queue/failed \
    /app/queue/images \
    /app/queue/topics \
    /app/queue/tmp

# Set ownership
RUN chown -R gaoding:gaoding /app

# Expose port
EXPOSE 8710

# Environment variables
ENV CORS_ORIGINS="http://localhost:5173"

# Switch to non-root user
USER gaoding

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8710/api/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8710"]
