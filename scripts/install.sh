#!/bin/bash

# WiFi Jammer Installation Script

echo "🔧 Installing WiFi Jammer Tool..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y \
    aircrack-ng \
    mdk3 \
    xterm \
    gnome-terminal \
    net-tools \
    wireless-tools \
    python3-pip \
    python3-dev \
    libpcap-dev \
    nmap

# Install Python dependencies
echo "🐍 Installing Python packages..."
pip3 install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p config
mkdir -p /etc/wifi-jammer

# Copy configuration files
echo "⚙️ Copying configuration..."
cp config/default.config /etc/wifi-jammer/
cp config/logging.conf /etc/wifi-jammer/

# Create executable script
echo "🚀 Creating executable..."
cat > /usr/local/bin/wifi-jammer << 'EOF'
#!/bin/bash
cd /usr/share/wifi-jammer
sudo python3 run.py "$@"
EOF

chmod +x /usr/local/bin/wifi-jammer

# Copy files to installation directory
echo "📋 Copying files..."
mkdir -p /usr/share/wifi-jammer
cp -r src /usr/share/wifi-jammer/
cp run.py /usr/share/wifi-jammer/
cp requirements.txt /usr/share/wifi-jammer/
cp -r config /usr/share/wifi-jammer/

# Set permissions
chmod -R 755 /usr/share/wifi-jammer
chmod +x /usr/share/wifi-jammer/run.py

echo "✅ Installation complete!"
echo "Run 'sudo wifi-jammer' to start the tool"