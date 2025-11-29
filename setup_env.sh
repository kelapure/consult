#!/bin/bash
# Helper script to set up .env file

echo "Setting up .env file..."

# Check if .env already exists
if [ -f .env ]; then
    echo ".env file already exists. Creating backup..."
    cp .env .env.backup
fi

# Create .env from example
cp .env.example .env

echo ""
echo "✅ Created .env file from template"
echo ""
echo "Please edit .env and add:"
echo "  1. Your ANTHROPIC_API_KEY (from https://console.anthropic.com/)"
echo "  2. Your GMAIL_EMAIL"
echo ""
echo "To edit: nano .env  (or use your preferred editor)"
echo ""
