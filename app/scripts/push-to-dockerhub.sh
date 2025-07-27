#!/bin/bash

# Discord Bot Docker Hub Push Script
# Usage: ./scripts/push-to-dockerhub.sh <your-dockerhub-username>

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the project root (parent directory of scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if tag is provided, otherwise use 'latest'
if [ -z "$1" ]; then
    echo "ℹ️  No tag provided, using 'latest'"
    echo "Usage: ./scripts/push-to-dockerhub.sh [tag]"
    echo "Example: ./scripts/push-to-dockerhub.sh v1.0"
else
    echo "🏷️  Using tag: $1"
fi

DOCKERHUB_USERNAME="samuelc595"
IMAGE_NAME="capitan-coditos"
TAG="${1:-latest}"
FULL_IMAGE_NAME="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"

echo "🐳 Building Capitán Coditos Discord Bot Docker image..."
# Change to project root and build from there
cd "$PROJECT_ROOT"
docker build -t "${IMAGE_NAME}:${TAG}" .

echo "🏷️ Tagging image for Docker Hub..."
docker tag "${IMAGE_NAME}:${TAG}" "${FULL_IMAGE_NAME}"

echo "🔐 Please log in to Docker Hub if you haven't already..."
docker login

echo "📤 Pushing image to Docker Hub..."
docker push "${FULL_IMAGE_NAME}"

echo "✅ Successfully pushed ${FULL_IMAGE_NAME} to Docker Hub!"
echo ""
echo "🚀 To run Capitán Coditos from Docker Hub:"
echo "   docker run -d \\"
echo "     --name capitan-coditos \\"
echo "     --restart unless-stopped \\"
echo "     -e DISCORD_TOKEN=\"your_token_here\" \\"
echo "     -e RIOT_API_KEY=\"your_riot_key_here\" \\"
echo "     -e OPENAI_API_KEY=\"your_openai_key_here\" \\"
echo "     ${FULL_IMAGE_NAME}"
echo ""
echo "📝 Don't forget to update the README.md with your Docker Hub username!"
