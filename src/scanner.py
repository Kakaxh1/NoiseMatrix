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
    def __init__(self, interface: str, config: Dict):
        self.interface = interface
        self.config = config
        self.networks: List[Dict] = []
        self.scan_process = None
        self.scan_complete = False
        
    def scan(self, duration: Optional[int] = None) -> List[Dict]:
        if not duration:
            duration = int(self.config.get('scan_timeout', '30'))
            
        try:
            console.print(f"[yellow]Scanning for {duration} seconds...[/yellow]")
            
            os.makedirs("/tmp/wifi_scan", exist_ok=True)
            
            subprocess.run(["sudo", "pkill", "-f", "airodump-ng"], stderr=subprocess.DEVNULL)
            
            cmd = [
                "sudo", "airodump-ng",
                self.interface,
                "--output-format", "csv",
                "--write", "/tmp/wifi_scan/scan",
                "--write-interval", "1"
            ]
            
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
            
            for i in range(duration):
                time.sleep(1)
                self.networks = self.parse_scan_results()
                console.print(f"Scanning... {duration - i}s remaining ({len(self.networks)} networks found)", end='\r')
                
            self.scan_process.terminate()
            self.scan_process.wait(timeout=5)
            
            self.networks = self.parse_scan_results()
            self.scan_complete = True
            
            console.print(f"\n[green]Found {len(self.networks)} networks[/green]")
            return self.networks
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            console.print(f"[red]Scan error: {e}[/red]")
            return []
            
    def parse_scan_results(self) -> List[Dict]:
        networks = []
        
        possible_files = [
            '/tmp/wifi_scan/scan-01.csv',
            '/tmp/wifi_scan/scan-01.kismet.csv',
            '/tmp/scan-01.csv'
        ]
        
        csv_file = None
        for file_path in possible_files:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                csv_file = file_path
                break
                
        if not csv_file:
            return networks
        
        try:
            time.sleep(0.5)
            
            with open(csv_file, 'r', errors='ignore') as f:
                content = f.read()
            
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            start_idx = -1
            for i, line in enumerate(lines):
                if 'BSSID' in line and 'ESSID' in line:
                    start_idx = i + 1
                    break
            
            if start_idx == -1:
                return networks
            
            for line in lines[start_idx:]:
                if 'Station MAC' in line or ('BSSID' in line and 'Station' in line):
                    break
                    
                if not line.strip() or line.startswith('BSSID'):
                    continue
                    
                parts = line.split(',')
                if len(parts) < 14:
                    continue
                    
                signal = '0'
                for i, part in enumerate(parts):
                    if part and 'dBm' in part:
                        signal = part.strip().replace('dBm', '')
                        break
                
                bssid = parts[0].strip().upper()
                if not bssid or len(bssid) < 12:
                    continue
                    
                network = {
                    'bssid': bssid,
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
                
                if network['bssid'] and network['bssid'] != 'BSSID' and len(network['bssid']) > 10:
                    networks.append(network)
                            
        except Exception as e:
            logger.error(f"Error parsing scan results: {e}")
            
        unique_networks = {}
        for network in networks:
            bssid = network['bssid']
            if bssid not in unique_networks:
                unique_networks[bssid] = network
            else:
                try:
                    current_signal = int(unique_networks[bssid].get('signal', '0') or '0')
                    new_signal = int(network.get('signal', '0') or '0')
                    if new_signal > current_signal:
                        unique_networks[bssid] = network
                except:
                    pass
                    
        return list(unique_networks.values())
        
    def save_results(self, filename: Optional[str] = None) -> str:
        """Save scan results with proper error handling"""
        if not self.networks:
            console.print("[red]No networks to save![/red]")
            return ""
            
        # Create logs directory
        os.makedirs("logs", exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/scan_{timestamp}.json"
        
        try:
            # Clean data for JSON
            clean_networks = []
            for network in self.networks:
                clean_net = {}
                for key, value in network.items():
                    if value is None:
                        clean_net[key] = ""
                    else:
                        clean_net[key] = str(value)
                clean_networks.append(clean_net)
            
            # Save to JSON
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
        if not self.networks:
            return "No networks found"
            
        total = len(self.networks)
        encrypted = sum(1 for n in self.networks if n.get('encryption') and n['encryption'] not in ['', 'OPN'])
        
        return f"Found {total} networks ({encrypted} encrypted)"
