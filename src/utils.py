"""
Utility functions
"""

import os
import sys
import subprocess
import signal
import re
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from datetime import datetime

console = Console()

def check_root() -> bool:
    """Check if script is running as root"""
    return os.geteuid() == 0

def load_config(config_path: Optional[str] = None, force_default: bool = False) -> Dict[str, Any]:
    """Load configuration from file"""
    import configparser
    config = configparser.ConfigParser()
    
    if force_default:
        config_path = "config/default.config"
        
    if config_path and os.path.exists(config_path):
        config.read(config_path)
    else:
        # Check alternative locations
        alt_paths = [
            "/etc/wifi-jammer/default.config",
            os.path.expanduser("~/.config/wifi-jammer/config")
        ]
        for path in alt_paths:
            if os.path.exists(path):
                config.read(path)
                break
        else:
            # Return default config
            config['DEFAULT'] = {
                'monitor_mode': 'true',
                'scan_timeout': '30',
                'packet_rate': '1000',
                'log_level': 'INFO'
            }
    
    # Convert to dict for easier access
    config_dict = {}
    if 'DEFAULT' in config:
        for key, value in config['DEFAULT'].items():
            config_dict[key] = value
    
    return config_dict

def validate_interface(interface: str) -> bool:
    """Validate network interface exists"""
    return os.path.exists(f"/sys/class/net/{interface}")

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def print_banner():
    """Print application banner"""
    banner = """
    ╔══════════════════════════════════════╗
    ║         WiFi Jammer v1.0.0           ║
    ║    Professional Deauth Tool          ║
    ║    FOR EDUCATIONAL USE ONLY          ║
    ╚══════════════════════════════════════╝
    """
    console.print(Panel(banner, style="cyan"))

def run_command(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run shell command safely"""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
        console.print(f"[red]Error: {e.stderr}[/red]")
        raise
    except FileNotFoundError:
        console.print(f"[red]Command not found: {cmd[0]}[/red]")
        console.print("[yellow]Make sure required tools are installed: aircrack-ng, mdk3[/yellow]")
        sys.exit(1)

def setup_signal_handlers(cleanup_func):
    """Setup signal handlers for clean exit"""
    cleanup_called = False
    
    def signal_handler(sig, frame):
        nonlocal cleanup_called
        if cleanup_called:
            return
            
        cleanup_called = True
        console.print("\n[yellow]Received interrupt signal...[/yellow]")
        try:
            cleanup_func()
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def parse_airodump_output(filename: str) -> List[Dict[str, Any]]:
    """Parse airodump-ng output file"""
    networks = []
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        # Basic parsing logic
        lines = content.split('\n')
        for line in lines:
            if 'BSSID' in line or 'Station' in line:
                continue
            parts = line.split(',')
            if len(parts) > 13:
                network = {
                    'bssid': parts[0].strip(),
                    'channel': parts[3].strip(),
                    'encryption': parts[5].strip(),
                    'essid': parts[13].strip().strip('"'),
                    'signal': parts[8].strip()
                }
                networks.append(network)
    except Exception as e:
        console.print(f"[red]Error parsing airodump output: {e}[/red]")
    
    return networks

def format_mac(mac: str) -> str:
    """Format MAC address with colons"""
    mac = re.sub(r'[^a-fA-F0-9]', '', mac)
    if len(mac) == 12:
        return ':'.join(mac[i:i+2].upper() for i in range(0, 12, 2))
    return mac

def validate_mac(mac: str) -> bool:
    """Validate MAC address format"""
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    return bool(re.match(pattern, mac))