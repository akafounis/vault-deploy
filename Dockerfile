FROM python:3.11-slim-bookworm

# System deps for Pillow
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create upload dirs (will be overridden by Cloud Run volume mounts if needed)
RUN mkdir -p uploads/projects uploads/thumbnails uploads/avatars static/videos

# Cloud Run sets PORT env var — default to 8080
ENV PORT=8080

# Use shell form so $PORT is expanded
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
