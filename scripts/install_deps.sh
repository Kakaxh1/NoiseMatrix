#!/bin/bash

# WiFi Jammer Dependencies Installer

echo "Installing WiFi Jammer dependencies..."

# Update package list
sudo apt-get update

# Install required system packages
sudo apt-get install -y \
    aircrack-ng \
    mdk3 \
    xterm \
    gnome-terminal \
    net-tools \
    wireless-tools \
    python3-pip \
    python3-dev \
    libpcap-dev

# Install Python dependencies
pip3 install -r requirements.txt

# Create necessary directories
mkdir -p logs
mkdir -p config

# Set permissions
chmod +x scripts/*.sh

echo "Installation complete!"