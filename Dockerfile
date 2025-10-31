FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py .
COPY main.py .
COPY src/ src/

# Create data directories
RUN mkdir -p data_cache memory_db results

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
