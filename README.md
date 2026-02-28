# NoiseMatrix

Professional WiFi Security Testing Tool for educational purposes.
Created by Kakaxh1

## Legal Disclaimer

This tool is for educational purposes only. Using it against networks without explicit permission is illegal in most jurisdictions. The author is not responsible for any misuse.

## Features

- Network scanning (2.4GHz and 5GHz bands)
- Deauthentication attack testing
- Target management system with save/load functionality
- Real-time attack monitoring with statistics
- Packet rate visualization
- Multiple attack intensities (low, medium, high)
- Quick attack with last target
- Scan results export to JSON
- Automatic monitor mode management
- Clean exit with interface restoration

## Requirements

- Linux operating system (Kali Linux, Parrot OS, or Ubuntu)
- Wireless adapter with monitor mode support
- Python 3.8 or higher
- Root privileges
- aircrack-ng suite
- mdk3 tool

## Installation

Clone the repository:
```bash
git clone https://github.com/Kakaxh1/NoiseMatrix.git
cd NoiseMatrix
Run the installation script:

bash
sudo ./scripts/install.sh
The installer will automatically:

Install required system packages

Install Python dependencies

Create necessary directories

Set proper permissions

Usage
Start the tool:

bash
sudo ./noisematrix
Main Menu Options
Scan Networks - Scan for available WiFi networks in your area

Saved Targets - View and manage previously saved targets

Launch Attack - Start deauthentication attack on selected target

Attack Status - Monitor current attack statistics

Quick Attack - Quickly attack the last scanned or saved target

Settings - Configure tool parameters

Help - View documentation and usage guide

About - Information about NoiseMatrix

Exit - Clean exit with monitor mode option

Attack Intensities
Low (300 packets/sec) - Less noticeable, good for testing

Medium (600 packets/sec) - Balanced performance

High (1000 packets/sec) - Maximum disruption

Directory Structure
text
NoiseMatrix/
├── noisematrix              # Main launcher script
├── requirements.txt         # Python dependencies
├── setup.py                 # Python package setup
├── config/                  # Configuration files
│   ├── default.config      # Default tool configuration
│   └── logging.conf        # Logging configuration
├── scripts/                 # Installation and utility scripts
│   ├── install.sh          # Main installer
│   ├── install_deps.sh     # Dependency installer
│   └── run.py              # Python runner
├── src/                     # Source code directory
│   ├── attacker.py         # Deauthentication attack module
│   ├── config.py           # Configuration management
│   ├── init.py             # Package initializer
│   ├── interface_manager.py # Network interface management
│   ├── logger.py           # Logging functionality
│   ├── main.py             # Main application
│   ├── scanner.py          # Network scanning module
│   └── utils.py            # Utility functions
├── logs/                    # Scan logs (created on use)
└── targets/                 # Saved targets (created on use)
Configuration
Edit config/default.config to customize:

ini
[DEFAULT]
monitor_mode = true
scan_timeout = 30
packet_rate = 1000
log_level = INFO
Output Files
Scan results: logs/scan_*.json

Saved targets: targets/saved_targets.json

Application logs: logs/noisematrix.log

Troubleshooting
Common Issues
Interface not in monitor mode

Run: sudo airmon-ng start wlan0

Or let the tool enable it automatically

Permission denied

Always run with sudo: sudo ./noisematrix

No wireless interfaces found

Check if adapter is connected

Run: iwconfig to list interfaces

mdk3 not found

Run installer again: sudo ./scripts/install.sh

Security Notes
Only use on networks you own or have written permission to test

Deauthentication attacks are detectable by network monitoring tools

Some countries have strict laws against WiFi interference

Always obtain proper authorization before testing

Author
Created by Kakaxh1

License
MIT License - Educational Use Only

Version History
v1.0.0 (2024) - Initial stable release

Basic network scanning

Deauthentication attacks

Target management

Real-time monitoring

Support
For issues or questions:

GitHub Issues: https://github.com/Kakaxh1/NoiseMatrix/issues

Email: [your-email]

Acknowledgments
aircrack-ng team for wireless tools

mdk3 developers

Python rich library for beautiful console output

text

## 2. Missing Files to Add

### A. Create .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.so
.Python
*.egg-info/
dist/
build/

# Logs and data
logs/
targets/
*.log
*.json
!logs/.gitkeep
!targets/.gitkeep

# System files
*.swp
*.swo
*~
.DS_Store

# Virtual environment
venv/
env/
ENV/
.venv/

# IDE
.vscode/
.idea/
*.code-workspace

# Project specific
*.pyc
*.pyo
*.pyd
.coverage
.coverage.*
*.cover
EOF
