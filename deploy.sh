#!/bin/bash

echo "🚀 Setting up X Automation Bot on Ubuntu Server..."

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv xvfb

# Install Playwright browser dependencies
sudo apt install -y \
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2

# Create project directory
mkdir -p ~/x_automation_bot
cd ~/x_automation_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create user data directory
mkdir -p ~/x_automation/user_data

# Start virtual display
sudo apt install -y xvfb
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &

# Make scripts executable
chmod +x deploy.sh

echo "✅ Setup completed successfully!"
echo "📝 Next steps:"
echo "1. Create .env file with your credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: streamlit run streamlit_app.py --server.port 8501"