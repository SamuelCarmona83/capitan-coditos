# Docker Hub Deployment Guide

## 🚀 Quick Start - Push to Docker Hub

### Step 1: Prepare Your Environment

1. Make sure Docker is installed and running on your machine
2. Have a Docker Hub account ready at [hub.docker.com](https://hub.docker.com)

### Step 2: Push to Docker Hub

Run the provided script with your Docker Hub username:

```bash
./scripts/push-to-dockerhub.sh YOUR_DOCKERHUB_USERNAME
```

Example:
```bash
./scripts/push-to-dockerhub.sh johnsmith
```

The script will:
- ✅ Build your Docker image
- ✅ Tag it properly for Docker Hub
- ✅ Prompt you to log in to Docker Hub
- ✅ Push the image to your repository

### Step 3: Update Documentation

After pushing, update the README.md file and replace all instances of `YOUR_USERNAME` with your actual Docker Hub username.

## 🐳 Manual Docker Hub Push (Alternative)

If you prefer to do it manually:

```bash
# 1. Build the image
docker build -t discbot .

# 2. Tag for Docker Hub (replace 'yourusername' with your Docker Hub username)
docker tag discbot yourusername/discbot:latest

# 3. Login to Docker Hub
docker login

# 4. Push to Docker Hub
docker push yourusername/discbot:latest
```

## 🏃‍♂️ Running from Docker Hub

Once your image is on Docker Hub, anyone can run your bot:

### Option 1: Direct Docker Run

```bash
docker run -d \
  --name discbot \
  --restart unless-stopped \
  -e DISCORD_TOKEN="your_discord_token" \
  -e RIOT_API_KEY="your_riot_api_key" \
  -e OPENAI_API_KEY="your_openai_api_key" \
  yourusername/discbot:latest
```

### Option 2: Using Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  discbot:
    image: yourusername/discbot:latest
    container_name: discbot
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - RIOT_API_KEY=${RIOT_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

Create a `.env` file with your credentials:

```env
DISCORD_TOKEN=your_discord_token_here
RIOT_API_KEY=your_riot_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Run with:

```bash
docker-compose up -d
```

## 📦 Image Variants

You can create different versions:

```bash
# Latest version
docker tag discbot yourusername/discbot:latest

# Specific version
docker tag discbot yourusername/discbot:v1.0

# Push both
docker push yourusername/discbot:latest
docker push yourusername/discbot:v1.0
```

## 🔍 Verification

After pushing, verify your image is available:

1. Check on Docker Hub: `https://hub.docker.com/r/yourusername/discbot`
2. Pull and test: `docker pull yourusername/discbot:latest`

## 🛡️ Security Best Practices

1. **Never include API keys in the image** - Always use environment variables
2. **Use specific version tags** in production instead of `latest`
3. **Regularly update base images** to get security patches
4. **Scan images for vulnerabilities** using `docker scan yourusername/discbot:latest`

## 📊 Monitoring

Monitor your containerized bot:

```bash
# View logs
docker logs -f discbot

# Check resource usage
docker stats discbot

# Check health
docker inspect discbot --format='{{.State.Health.Status}}'
```

## 🔄 Updates

To update your bot:

1. Make code changes
2. Rebuild and push:
   ```bash
   ./scripts/push-to-dockerhub.sh yourusername
   ```
3. Update running containers:
   ```bash
   docker pull yourusername/discbot:latest
   docker-compose down
   docker-compose up -d
   ```

## 🆘 Troubleshooting

### Common Issues:

1. **Permission denied**: Make sure the script is executable: `chmod +x scripts/push-to-dockerhub.sh`
2. **Docker login issues**: Use `docker logout` then `docker login`
3. **Image too large**: Check `.dockerignore` is working properly
4. **Build failures**: Ensure all dependencies are in `requirements.txt`

### Getting Help:

- Check container logs: `docker logs discbot`
- Inspect container: `docker inspect discbot`
- Debug interactively: `docker run -it yourusername/discbot:latest /bin/bash`
