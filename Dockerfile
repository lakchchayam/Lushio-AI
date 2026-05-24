FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Cloud Run uses port 8080 by default
EXPOSE 8080

# Start FastAPI server - GCP Cloud Run uses PORT env var (default 8080)
CMD ["sh", "-c", "uvicorn src.agent:app_instance --host 0.0.0.0 --port ${PORT:-8080}"]
