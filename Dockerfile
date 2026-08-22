# Use the official Microsoft Playwright image as the base.
# Contains all OS-level dependencies (X11, fonts, libnss3) required for headless Chromium.
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Tor is used only as a local client SOCKS route; the entrypoint binds it to loopback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tor \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables to optimize Python for Docker
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create the sessions directory with least-privilege permissions.
# The current entrypoint runs as the image user, so no world-writable directory is required.
RUN mkdir -p sessions && chmod 700 sessions

# Copy the rest of the application code
COPY . .

# Run Tor (when enabled) and the bot under the supervised entrypoint.
RUN chmod 755 start.sh
CMD ["./start.sh"]


