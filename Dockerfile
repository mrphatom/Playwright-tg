# Use the official Microsoft Playwright image as the base.
# Contains all OS-level dependencies (X11, fonts, libnss3) required for headless Chromium.
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set environment variables to optimize Python for Docker
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create the sessions directory with appropriate permissions
RUN mkdir -p sessions && chmod 777 sessions

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["python", "bot.py"]


