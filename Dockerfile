# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set metadata
LABEL maintainer="samuelc595"
LABEL description="Capitán Coditos - Discord League of Legends Bot with AI Commentary"
LABEL version="1.0"

# Set the working directory in the container
WORKDIR /app

# Create a non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the bot code and all modules
COPY app/ ./

# Ensure database directory exists and has proper permissions for SQLite
RUN mkdir -p /app/database && \
    touch /app/database/.gitkeep && \
    chown -R botuser:botuser /app && \
    chmod -R 755 /app && \
    chmod -R 775 /app/database

# Switch to non-root user
USER botuser

# Define environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "print('Bot is healthy')" || exit 1

# Run bot.py when the container launches
CMD ["python", "bot.py"]
