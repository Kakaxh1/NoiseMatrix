"""
Network scanning module
"""

import subprocess
import re
import csv
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt

from src.logger import get_logger
from src.utils import parse_airodump_output

console = Console()
logger = get_logger(__name__)

class WiFiScanner:
    """Scan for WiFi networks"""
    
    def __init__(self, interface: str, config: Dict):
        self.interface = interface
        self.config = config
        self.networks: List[Dict] = []
        self.scan_process = None
        self.scan_complete = False
        
    def scan(self, duration: Optional[int] = None) -> List[Dict]:
        """Scan for networks"""
        if not duration:
            duration = int(self.config.get('scan_timeout', '30'))
            
        try:
            console.print(f"[yellow]Scanning for {duration} seconds...[/yellow]")
            
            # Ensure temp directory exists
            os.makedirs("/tmp/wifi_scan", exist_ok=True)
            
            # Kill any existing airodump processes
            subprocess.run(["sudo", "pkill", "-f", "airodump-ng"], stderr=subprocess.DEVNULL)
            
            # Start airodump-ng
            cmd = [
                "sudo", "airodump-ng",
                self.interface,
                "--output-format", "csv",
                "--write", "/tmp/wifi_scan/scan",
                "--write-interval", "1"
            ]
            
            # Add band selection if configured
            band = self.config.get('frequency_band', 'all')
            if band == "2.4ghz":
                cmd.extend(["--band", "bg"])
            elif band == "5ghz":
                cmd.extend(["--band", "a"])
            
            self.scan_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Show progress
            for i in range(duration):
                time.sleep(1)
                # Try to parse incremental results
                self.networks = self.parse_scan_results()
                console.print(f"Scanning... {duration - i}s remaining ({len(self.networks)} networks found)", end='\r')
                
            # Stop scan
            self.scan_process.terminate()
            self.scan_process.wait(timeout=5)
            
            # Final parse
            self.networks = self.parse_scan_results()
            self.scan_complete = True
            
            console.print(f"\n[green]Found {len(self.networks)} networks[/green]")
            return self.networks
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            console.print(f"[red]Scan error: {e}[/red]")
            return []
            
    def parse_scan_results(self) -> List[Dict]:
        """Parse airodump-ng CSV output"""
        networks = []
        
        # Try multiple possible file locations
        possible_files = [
            '/tmp/wifi_scan/scan-01.csv',
            '/tmp/wifi_scan/scan-01.kismet.csv',
            '/tmp/scan-01.csv'
        ]
        
        csv_file = None
        for file_path in possible_files:
            if os.path.exists(file_path):
                csv_file = file_path
                break
                
        if not csv_file:
            return networks
            
        try:
            with open(csv_file, 'r', errors='ignore') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            # Find where network data ends and station data begins
            in_networks = True
            for line in lines:
                if not line.strip():
                    continue
                    
                if "Station MAC" in line or "BSSID" in line and "Station" in line:
                    in_networks = False
                    continue
                    
                if in_networks and line.strip() and not line.startswith('BSSID'):
                    parts = line.split(',')
                    if len(parts) >= 14:
                        # Extract signal strength
                        signal = '0'
                        for i, part in enumerate(parts):
                            if part.strip().endswith('dBm'):
                                signal = part.strip().replace('dBm', '')
                                break
                        
                        network = {
                            'bssid': parts[0].strip().upper(),
                            'channel': parts[3].strip() if len(parts) > 3 else '0',
                            'speed': parts[4].strip() if len(parts) > 4 else '',
                            'encryption': parts[5].strip() if len(parts) > 5 else '',
                            'cipher': parts[6].strip() if len(parts) > 6 else '',
                            'authentication': parts[7].strip() if len(parts) > 7 else '',
                            'signal': signal,
                            'beacons': parts[9].strip() if len(parts) > 9 else '',
                            'iv': parts[10].strip() if len(parts) > 10 else '',
                            'lan_ip': parts[11].strip() if len(parts) > 11 else '',
                            'id_length': parts[12].strip() if len(parts) > 12 else '',
                            'essid': parts[13].strip().strip('"') if len(parts) > 13 else '[hidden]',
                        }
                        
                        # Only add if we have a valid BSSID
                        if network['bssid'] and network['bssid'] != 'BSSID' and len(network['bssid']) > 10:
                            networks.append(network)
                            
        except Exception as e:
            logger.error(f"Error parsing scan results: {e}")
            
        # Remove duplicates (keep strongest signal)
        unique_networks = {}
        for network in networks:
            bssid = network['bssid']
            if bssid not in unique_networks:
                unique_networks[bssid] = network
            else:
                # Keep the one with stronger signal
                try:
                    current_signal = int(unique_networks[bssid].get('signal', '0') or '0')
                    new_signal = int(network.get('signal', '0') or '0')
                    if new_signal > current_signal:
                        unique_networks[bssid] = network
                except:
                    pass
                    
        return list(unique_networks.values())
        
    def save_results(self, filename: Optional[str] = None) -> str:
        """Save scan results to file"""
        if not self.networks:
            console.print("[red]No networks to save![/red]")
            return ""
            
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/scan_{timestamp}.json"
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        try:
            # Clean up data for JSON serialization
            clean_networks = []
            for network in self.networks:
                clean_net = {}
                for key, value in network.items():
                    # Convert all values to strings and handle None
                    if value is None:
                        clean_net[key] = ""
                    else:
                        clean_net[key] = str(value)
                clean_networks.append(clean_net)
            
            with open(filename, 'w') as f:
                json.dump({
                    'scan_time': datetime.now().isoformat(),
                    'interface': self.interface,
                    'total_networks': len(clean_networks),
                    'networks': clean_networks
                }, f, indent=2)
                
            logger.info(f"Scan results saved to {filename}")
            console.print(f"[green]✓ Results saved to {filename}[/green]")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            console.print(f"[red]Error saving results: {e}[/red]")
            return ""

    def get_networks_summary(self) -> str:
        """Get a summary of found networks"""
        if not self.networks:
            return "No networks found"
            
        total = len(self.networks)
        encrypted = sum(1 for n in self.networks if n.get('encryption') and n['encryption'] not in ['', 'OPN'])
        
        return f"Found {total} networks ({encrypted} encrypted)"