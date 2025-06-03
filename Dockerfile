FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y    aria2    ffmpeg    wget    curl    git    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p downloads
RUN mkdir -p logs

# Set permissions
RUN chmod +x /app

# Start the bot
CMD ["python", "main.py"]
