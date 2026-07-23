# Use the official Microsoft Playwright image as the base.
# This is CRITICAL because it contains all the OS-level dependencies (fonts, libnss3, etc.) 
# required to run headless Chromium without crashing.
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["python", "bot.py"]

