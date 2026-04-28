FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port (Render uses $PORT env var dynamically)
EXPOSE 10000

# Start FastAPI server using Render's $PORT
CMD ["sh", "-c", "uvicorn src.agent:app_instance --host 0.0.0.0 --port ${PORT:-10000}"]
