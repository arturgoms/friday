FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy minimal requirements file (no ML packages - vLLM runs on remote machine)
COPY requirements-docker.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create logs directory
RUN mkdir -p /app/logs /app/data

# Default command (overridden in docker-compose)
CMD ["python", "-m", "src.interfaces.telegram.run"]
