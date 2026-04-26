# Use the official Python image (Debian-based for better library compatibility)
FROM python:3.10-slim

# Install system dependencies required for ctranslate2 and audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy dependency list first (to leverage Docker cache)
COPY requirements.txt .

# Install Python dependencies (allow ctranslate2 to find a compatible version)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Expose the port Render expects
EXPOSE 10000

# Command to run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]