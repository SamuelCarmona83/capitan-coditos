# Capitán Coditos - Discord League of Legends Bot

A Discord bot that provides League of Legends match analysis using the Riot API and OpenAI for entertaining match summaries.

## Features

- 📊 **Last Match Analysis** (`/ultimapartida`) - Get your latest LoL match stats with AI-powered commentary
- 🔍 **Team Analysis** (`/analizarpartida`) - Analyze your team's performance and find the worst performer with humor
- 🤖 **AI-Powered Commentary** - Sarcastic and brutally honest match analysis using OpenAI
- 🎮 **Riot ID Support** - Works with new Riot ID format (Name#Tag)

## 🐳 Docker Hub

### Quick Start with Docker

```bash
# Pull the image from Docker Hub
docker pull samuelc595/capitan-coditos:latest

# Run with environment variables
docker run -d \
  --name capitan-coditos \
  --restart unless-stopped \
  -e DISCORD_TOKEN="your_discord_bot_token" \
  -e RIOT_API_KEY="your_riot_api_key" \
  -e OPENAI_API_KEY="your_openai_api_key" \
  samuelc595/capitan-coditos:latest
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token from Discord Developer Portal | ✅ |
| `RIOT_API_KEY` | Your Riot Games API key from Riot Developer Portal | ✅ |
| `OPENAI_API_KEY` | Your OpenAI API key for AI commentary | ✅ |

## 🚀 Deployment Options

### Option 1: Docker Run

```bash
docker run -d \
  --name capitan-coditos \
  --restart unless-stopped \
  -e DISCORD_TOKEN="YOUR_DISCORD_TOKEN_HERE" \
  -e RIOT_API_KEY="YOUR_RIOT_API_KEY_HERE" \
  -e OPENAI_API_KEY="YOUR_OPENAI_API_KEY_HERE" \
  samuelc595/capitan-coditos:latest
```

### Option 2: Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  capitan-coditos:
    image: samuelc595/capitan-coditos:latest
    container_name: capitan-coditos
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - RIOT_API_KEY=${RIOT_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    # Optional: if you want to persist logs
    volumes:
      - ./logs:/app/logs
```

Create a `.env` file:

```env
DISCORD_TOKEN=your_discord_bot_token_here
RIOT_API_KEY=your_riot_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Then run:

```bash
docker-compose up -d
```

### Option 3: Local Development

```bash
# Clone the repository
git clone https://github.com/samuelc595/discbot.git
cd discbot

# Build the image
docker build -t capitan-coditos .

# Run with environment file
docker run -d --env-file .env capitan-coditos
```

## 🎮 Bot Commands

### `/ultimapartida <riot_id>`

Analyzes your last League of Legends match with AI commentary.

**Example:**
```
/ultimapartida Roga#LAN
```

**Response:**
```
**Roga#LAN** jugó como **Jinx**
🎯 KDA: 12/3/8 | 🎮 Victoria | 🕒 31 minutos

**¡Finalmente alguien que sabe usar un mouse!** Tu KDA de `12/3/8` con `45,231` de daño en 31 minutos demuestra que no todos los días hay que jugar *Candy Crush*. 🎯
```

### `/analizarpartida <riot_id>`

Analyzes your team's performance and roasts the worst performer.

**Example:**
```
/analizarpartida Roga#LAN
```

**Response:**
```
🏆 **Victoria** - ⏱️ 31 min
**Equipo de Roga#LAN:**
• **Roga** - Jinx (`12/3/8`)
• **Player2** - Yasuo (`2/8/4`)
• **Player3** - Thresh (`1/5/12`)
• **Player4** - Graves (`8/4/6`)
• **Player5** - Orianna (`6/2/9`)

**Player2**, con tu impresionante `2/8/4` como *Yasuo*, has demostrado que el daño de `8,432` en 31 minutos es perfecto para... __¿tal vez probar *Minecraft*?__ ~~Ese 0.75 KDA~~ grita "modo espectador activado". 🎮
```

## 🔧 Setup Requirements

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token
5. Enable necessary intents (Message Content Intent if needed)
6. Invite bot to your server with appropriate permissions

### Riot API Key

1. Visit [Riot Developer Portal](https://developer.riotgames.com/)
2. Sign in with your Riot account
3. Generate a personal API key
4. For production, apply for a production API key

### OpenAI API Key

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Create an account or sign in
3. Go to API Keys section
4. Create a new API key

## 🛠️ Development

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/samuelc595/discbot.git
cd discbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your API keys

# Run the bot
python bot.py
```

### Building Custom Image

```bash
# Build the image
docker build -t samuelc595/capitan-coditos:latest .

# Test locally
docker run --env-file .env samuelc595/capitan-coditos:latest

# Push to Docker Hub
docker push samuelc595/capitan-coditos:latest
```

## 📝 Container Management

### View Logs

```bash
# View container logs
docker logs discbot

# Follow logs in real-time
docker logs -f discbot
```

### Update Bot

```bash
# Pull latest image
docker pull YOUR_USERNAME/discbot:latest

# Stop and remove old container
docker stop discbot
docker rm discbot

# Run new container
docker run -d \
  --name discbot \
  --restart unless-stopped \
  --env-file .env \
  YOUR_USERNAME/discbot:latest
```

### Health Check

```bash
# Check if container is running
docker ps | grep discbot

# Check container resource usage
docker stats discbot
```

## 🐛 Troubleshooting

### Common Issues

1. **Bot not responding**: Check if the Discord token is correct and the bot is invited to the server
2. **Riot API errors**: Verify your Riot API key is valid and not rate-limited
3. **OpenAI errors**: Check your OpenAI API key and account balance
4. **Container crashes**: Check logs with `docker logs discbot`

### Debug Mode

To run with more verbose logging:

```bash
docker run -d \
  --name discbot \
  --restart unless-stopped \
  --env-file .env \
  -e PYTHONUNBUFFERED=1 \
  YOUR_USERNAME/discbot:latest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker
5. Submit a pull request

## 🔗 Links

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Riot Developer Portal](https://developer.riotgames.com/)
- [OpenAI Platform](https://platform.openai.com/)
- [Docker Hub Repository](https://hub.docker.com/r/samuelc595/capitan-coditos)

---

Made with ❤️ for the League of Legends community
