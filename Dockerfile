# Use official Python slim image
FROM python:3.11-slim

# Set system environment configurations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TRIPFORGE_WEB_MODE=true \
    PORT=8080

# Create and set the working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install python dependencies, gunicorn, and the package
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn && \
    pip install --no-cache-dir -e .

# Copy the application source code
COPY . .

# Expose target container port
EXPOSE 8080

# Run the Flask app with gunicorn
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app:app
