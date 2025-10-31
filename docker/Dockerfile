FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements/prod.txt requirements/prod.txt
COPY requirements/base.txt requirements/base.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy application code
COPY src/ src/
COPY config/ config/

# Create necessary directories
RUN mkdir -p /app/data_cache /app/memory_db /app/results

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV TRADING_ENV=production

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the application
CMD ["python", "-m", "src.main"]
