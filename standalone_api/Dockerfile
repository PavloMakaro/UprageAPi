FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    xargs -a apt.txt apt-get install -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose API port
EXPOSE 20067

# Run the API server
CMD ["python", "api_server.py"]
