#!/bin/bash

# Capitán Coditos - Docker Hub Deployment Verification Script

echo "🎮 Capitán Coditos - Discord Bot Deployment Verification"
echo "============================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root (parent directory of scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is running"

# Pull the latest image
echo "📥 Pulling latest image from Docker Hub..."
docker pull samuelc595/capitan-coditos:latest

if [ $? -eq 0 ]; then
    echo "✅ Successfully pulled samuelc595/capitan-coditos:latest"
else
    echo "❌ Failed to pull image from Docker Hub"
    exit 1
fi

# Show image info
echo ""
echo "📋 Image Information:"
docker images samuelc595/capitan-coditos:latest --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
echo "🚀 Ready to deploy! Use one of these commands:"
echo ""
echo "Option 1 - Quick start with environment variables:"
echo "docker run -d \\"
echo "  --name capitan-coditos \\"
echo "  --restart unless-stopped \\"
echo "  -e DISCORD_TOKEN=\"your_discord_token\" \\"
echo "  -e RIOT_API_KEY=\"your_riot_api_key\" \\"
echo "  -e OPENAI_API_KEY=\"your_openai_api_key\" \\"
echo "  samuelc595/capitan-coditos:latest"
echo ""
echo "Option 2 - Using docker-compose:"
echo "docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "🔗 Docker Hub Repository: https://hub.docker.com/r/samuelc595/capitan-coditos"
echo "📚 Full Documentation: README.md"
