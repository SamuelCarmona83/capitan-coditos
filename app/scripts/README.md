# Scripts

This folder contains utility scripts for the Capitán Coditos Discord bot.

## Available Scripts

### `push-to-dockerhub.sh`

Builds and pushes the Docker image to Docker Hub.

**Usage:**
```bash
# From project root
./scripts/push-to-dockerhub.sh [tag]

# Examples
./scripts/push-to-dockerhub.sh          # Uses 'latest' tag
./scripts/push-to-dockerhub.sh v1.0     # Uses 'v1.0' tag
```

**What it does:**
- Changes to project root directory
- Builds Docker image from Dockerfile
- Tags image for Docker Hub
- Prompts for Docker Hub login
- Pushes image to Docker Hub repository

### `verify-deployment.sh`

Verifies that the Docker image is available on Docker Hub and provides deployment instructions.

**Usage:**
```bash
# From project root
./scripts/verify-deployment.sh
```

**What it does:**
- Checks if Docker is running
- Pulls the latest image from Docker Hub
- Shows image information
- Displays deployment commands

## Prerequisites

- Docker installed and running
- Docker Hub account (for push script)
- Executable permissions on scripts

## Making Scripts Executable

If needed, make the scripts executable:

```bash
chmod +x scripts/*.sh
```

## Notes

- All scripts are designed to be run from the project root
- The push script automatically changes to the project root to ensure correct Docker build context
- Environment variables should be set separately when running containers
