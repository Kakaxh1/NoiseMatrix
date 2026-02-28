"""
Network interface management module
"""

import os
import subprocess
import time
import re
from typing import Optional, List, Dict, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.utils import run_command
from src.logger import get_logger

console = Console()
logger = get_logger(__name__)

class InterfaceManager:
    """Manage network interfaces and monitor mode"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.interface = None
        self.original_interface_state: Dict = {}
        
    def get_interfaces(self) -> List[Tuple[str, str]]:
        """Get list of available network interfaces with their modes"""
        try:
            # Get all network interfaces
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True
            )
            interfaces = []
            for line in result.stdout.split('\n'):
                if ': ' in line and not line.startswith(' '):
                    iface = line.split(': ')[1].split('@')[0]
                    if iface != 'lo':  # Skip loopback
                        mode = self.get_current_mode(iface)
                        if self.is_wireless(iface):
                            interfaces.append((iface, mode))
            
            return interfaces
        except Exception as e:
            logger.error(f"Error getting interfaces: {e}")
            return []
            
    def is_wireless(self, interface: str) -> bool:
        """Check if interface is wireless"""
        try:
            result = subprocess.run(
                ["iwconfig", interface],
                capture_output=True,
                text=True
            )
            return "IEEE 802.11" in result.stdout
        except:
            return False
            
    def check_monitor_mode(self, interface: str) -> bool:
        """Check if interface is in monitor mode"""
        mode = self.get_current_mode(interface)
        return mode == "monitor"
        
    def get_current_mode(self, interface: str) -> str:
        """Get current mode of interface"""
        try:
            result = subprocess.run(
                ["iwconfig", interface],
                capture_output=True,
                text=True
            )
            if "Mode:Monitor" in result.stdout:
                return "monitor"
            elif "Mode:Managed" in result.stdout:
                return "managed"
            elif "Mode:Master" in result.stdout:
                return "master (AP)"
            elif "Mode:Repeater" in result.stdout:
                return "repeater"
            elif "Mode:Secondary" in result.stdout:
                return "secondary"
            else:
                # Try to determine from flags
                if "UP" in result.stdout and "RUNNING" in result.stdout:
                    return "active"
                return "unknown"
        except:
            return "unknown"
            
    def get_interface_details(self, interface: str) -> Dict:
        """Get detailed information about interface"""
        details = {
            'name': interface,
            'mode': self.get_current_mode(interface),
            'mac': self.get_mac_address(interface),
            'driver': self.get_driver(interface),
            'chipset': self.get_chipset(interface)
        }
        return details
        
    def get_mac_address(self, interface: str) -> str:
        """Get MAC address of interface"""
        try:
            result = subprocess.run(
                ["cat", f"/sys/class/net/{interface}/address"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip().upper()
        except:
            return "Unknown"
            
    def get_driver(self, interface: str) -> str:
        """Get driver for interface"""
        try:
            # Try to get driver from ethtool
            result = subprocess.run(
                ["ethtool", "-i", interface],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if 'driver:' in line:
                    return line.split('driver:')[1].strip()
            return "Unknown"
        except:
            return "Unknown"
            
    def get_chipset(self, interface: str) -> str:
        """Get chipset information"""
        try:
            # Try to get from lsusb
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True
            )
            # This is simplified - would need more complex parsing
            return "Unknown"
        except:
            return "Unknown"
            
    def setup_interface(self) -> Optional[str]:
        """Setup network interface for monitoring"""
        interfaces = self.get_interfaces()
        
        if not interfaces:
            console.print("[red]No wireless interfaces found![/red]")
            console.print("[yellow]Make sure you have a WiFi adapter connected[/yellow]")
            return None
            
        # Show interface selection menu
        console.print("[cyan]Available wireless interfaces:[/cyan]")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Interface", style="green")
        table.add_column("Mode", style="yellow")
        table.add_column("MAC Address", style="blue")
        
        for i, (iface, mode) in enumerate(interfaces, 1):
            mac = self.get_mac_address(iface)
            # Color code mode
            if mode == "monitor":
                mode_display = f"[green]{mode}[/green]"
            elif mode == "managed":
                mode_display = f"[yellow]{mode}[/yellow]"
            else:
                mode_display = f"[red]{mode}[/red]"
                
            table.add_row(str(i), iface, mode_display, mac)
            
        console.print(table)
        console.print()
        
        # Let user choose
        try:
            choice = Prompt.ask(
                "[cyan]Select interface number[/cyan]",
                choices=[str(i) for i in range(1, len(interfaces)+1)]
            )
            interface = interfaces[int(choice) - 1][0]
        except (ValueError, IndexError):
            console.print("[red]Invalid choice![/red]")
            return None
            
        # Check current mode
        current_mode = self.get_current_mode(interface)
        console.print(f"\n[cyan]Selected interface: {interface}[/cyan]")
        console.print(f"[cyan]Current mode: {current_mode}[/cyan]")
        
        # Handle monitor mode
        if current_mode != "monitor":
            console.print()
            if self.config.get('monitor_mode', 'true').lower() == 'true':
                console.print("[yellow]Interface is not in monitor mode[/yellow]")
                if Confirm.ask("[cyan]Enable monitor mode now?[/cyan]", default=True):
                    if not self.enable_monitor_mode(interface):
                        return None
                else:
                    console.print("[red]Monitor mode is required for attacks![/red]")
                    if not Confirm.ask("[yellow]Continue anyway?[/yellow]"):
                        return None
                    self.interface = interface
            else:
                self.interface = interface
        else:
            console.print("[green]✓ Interface already in monitor mode[/green]")
            self.interface = interface
            
        return self.interface
        
    def enable_monitor_mode(self, interface: str) -> bool:
        """Enable monitor mode on interface"""
        try:
            console.print(f"[yellow]Enabling monitor mode on {interface}...[/yellow]")
            
            # Save original state
            self.original_interface_state[interface] = {
                'mode': self.get_current_mode(interface)
            }
            
            # Kill interfering processes
            console.print("[dim]Stopping interfering processes...[/dim]")
            subprocess.run(["sudo", "airmon-ng", "check", "kill"], 
                         capture_output=True)
            
            # Enable monitor mode
            result = subprocess.run(
                ["sudo", "airmon-ng", "start", interface],
                capture_output=True,
                text=True
            )
            
            time.sleep(2)
            
            # Check if interface name changed (e.g., wlan0 -> wlan0mon)
            mon_interface = f"{interface}mon"
            if os.path.exists(f"/sys/class/net/{mon_interface}"):
                self.interface = mon_interface
                interface = mon_interface
            else:
                self.interface = interface
            
            # Verify monitor mode
            if self.check_monitor_mode(interface):
                console.print(f"[green]✓ Monitor mode enabled on {self.interface}[/green]")
                return True
            else:
                console.print("[red]Failed to enable monitor mode[/red]")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling monitor mode: {e}")
            console.print(f"[red]Error: {e}[/red]")
            return False
            
    def disable_monitor_mode(self):
        """Disable monitor mode and restore interface"""
        if not self.interface:
            return
            
        try:
            console.print(f"[yellow]Disabling monitor mode on {self.interface}...[/yellow]")
            
            # Stop monitor mode
            subprocess.run(
                ["sudo", "airmon-ng", "stop", self.interface],
                capture_output=True
            )
            
            # Restart network manager
            subprocess.run(
                ["sudo", "systemctl", "start", "NetworkManager"],
                capture_output=True
            )
            
            # Try to restore original interface name
            base_interface = self.interface.replace('mon', '')
            if base_interface != self.interface and os.path.exists(f"/sys/class/net/{base_interface}"):
                self.interface = base_interface
            
            console.print("[green]✓ Monitor mode disabled[/green]")
            
        except Exception as e:
            logger.error(f"Error disabling monitor mode: {e}")
            
    def cleanup(self):
        """Cleanup interface settings"""
        if self.interface:
            # Only disable if we enabled it
            if self.original_interface_state.get(self.interface.replace('mon', '')):
                self.disable_monitor_mode()