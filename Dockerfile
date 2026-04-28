FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Upgrade pip first to ensure latest resolver
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install with no cache (forces fresh install)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify critical imports exist (will fail build early if something is missing)
RUN python -c "from langchain_groq import ChatGroq; print('langchain_groq OK')"
RUN python -c "from mcp import ClientSession; print('mcp OK')"

# Copy application files
COPY . .

# Expose port (Render uses $PORT env var dynamically)
EXPOSE 10000

# Start FastAPI server using Render's $PORT
CMD ["sh", "-c", "uvicorn src.agent:app_instance --host 0.0.0.0 --port ${PORT:-10000}"]
