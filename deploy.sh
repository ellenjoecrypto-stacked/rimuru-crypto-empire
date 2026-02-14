#!/bin/bash

# RIMURU CRYPTO EMPIRE - Deployment Script
# Automated setup and deployment

set -e

echo "🚀 RIMURU CRYPTO EMPIRE - Deployment"
echo "======================================"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is not installed. Please install Docker first."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is not installed. Please install Docker Compose first."; exit 1; }

# Create .env file if not exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env file and set secure passwords before continuing!"
    echo "   nano .env"
    read -p "Press Enter after editing .env..."
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/bot_states data/ai_models logs

# Set permissions
chmod 755 data logs

# Pull Ollama model
echo "🤖 Pulling Ollama model..."
docker-compose up -d ollama
sleep 5
docker-compose exec -T ollama ollama pull llama2 || echo "⚠️  Could not pull Ollama model (will try later)"

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo ""
echo "📊 Service Status:"
echo "=================="
docker-compose ps

echo ""
echo "✅ Deployment Complete!"
echo "======================"
echo ""
echo "📱 Access Points:"
echo "   Frontend Dashboard: http://localhost:3000"
echo "   API Documentation: http://localhost:8000/docs"
echo "   Ollama AI:         http://localhost:11434"
echo ""
echo "📋 Next Steps:"
echo "   1. Access the dashboard at http://localhost:3000"
echo "   2. Add your exchange API keys in the Security section"
echo "   3. Create and configure trading bots"
echo "   4. Start with PAPER TRADING mode"
echo "   5. Monitor performance and adjust strategies"
echo ""
echo "📖 Documentation: See README.md for detailed instructions"
echo ""
echo "⚠️  IMPORTANT REMINDERS:"
echo "   - Never enable withdrawal permissions on API keys"
echo "   - Use IP whitelisting on exchanges"
echo "   - Start with paper trading"
echo "   - Set strict loss limits"
echo "   - Keep your vault password secure"
echo ""