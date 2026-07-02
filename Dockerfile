# ==============================================================================
# BASE IMAGE DEFINITION
# ==============================================================================
# Use the official lightweight Python slim image to keep the container small,
# reduce cold-start latency, and minimize the attack surface in Cloud Run.
FROM python:3.11-slim

# ==============================================================================
# ENVIRONMENT VARIABLES CONFIGURATION
# ==============================================================================
# Configure critical container variables:
# - PYTHONUNBUFFERED: Prevents Python from buffering stdout/stderr (crucial for streaming logs in real time to Cloud Logging).
# - PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk (reduces unnecessary disk writes on ephemeral systems).
# - TRIPFORGE_WEB_MODE: Forces the web server configuration to boot into active UI mode.
# - PORT: Default port requested by Cloud Run (will be dynamically set by the platform at runtime, default to 8080).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TRIPFORGE_WEB_MODE=true \
    PORT=8080

# ==============================================================================
# WORKING DIRECTORY SETUP
# ==============================================================================
# Create and set the base directory for the containerized application.
WORKDIR /app

# ==============================================================================
# DEPENDENCIES INSTALLATION
# ==============================================================================
# Copy only the package metadata and dependency configuration files first.
# This leverages Docker's layer caching mechanism, meaning dependencies are only
# reinstalled if these files change (significantly speeds up subsequent cloud builds).
COPY requirements.txt pyproject.toml ./

# Install python dependencies and gunicorn (the WSGI server needed for production).
# We use --no-cache-dir to prevent package cache bloating the final container image size.
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# ==============================================================================
# APPLICATION CODE COPY
# ==============================================================================
# Copy the entire workspace directory containing the source files, static assets,
# databases, and HTML templates into the active container workdir.
COPY . .

# Install the local package in editable/development mode inside the container.
# This registers the `tripforge` library namespace, enabling internal relative imports.
RUN pip install --no-cache-dir -e .

# ==============================================================================
# PORTS & BOOT COMMAND
# ==============================================================================
# Expose port 8080 to match Cloud Run's default routing configuration.
EXPOSE 8080

# Run the Flask web application using Gunicorn as the WSGI server for production.
# Cloud Run starts the server by passing the PORT environment variable.
# Arguments:
# - --bind 0.0.0.0:$PORT: Listens to all network interfaces on the cloud-allocated port.
# - --workers 1 --threads 8: Safe serverless configuration preventing CPU throttling.
# - --timeout 0: Disables timeouts to allow long-running SSE connections to stream itineraries.
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app:app

