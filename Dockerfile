# ==============================================================================
# Stage 1: Build React Frontend
# ==============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy frontend dependency manifests and install
COPY badge-generator_Frontend/package*.json ./
RUN npm ci || npm install

# Copy frontend source code and build production bundle
COPY badge-generator_Frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend & Static Server
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

# Install system dependencies for Tesseract OCR, CairoSVG, and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install python packages
COPY badge-generator_Backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY badge-generator_Backend/ ./

# Copy built frontend static assets into backend static folder
COPY --from=frontend-builder /app/frontend/dist ./static

# Expose Render default port
EXPOSE 10000

# Start FastAPI server using uvicorn (Render dynamically sets $PORT)
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]
