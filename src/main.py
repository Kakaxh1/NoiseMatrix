#!/usr/bin/env python3
"""
NoiseMatrix - Main Application
Created by Kkaxh1
"""

import os
import sys
import signal
import argparse
import time
import json
from typing import Optional, List, Dict
from datetime import datetime

# Rich imports for beautiful console output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.columns import Columns
    from rich import box
except ImportError:
    print("Error: Rich library not installed. Please run: pip install rich")
    sys.exit(1)

# Local imports
try:
    from src.interface_manager import InterfaceManager
    from src.scanner import WiFiScanner
    from src.attacker import DeauthAttacker
    from src.utils import (
        check_root,
        load_config,
        clear_screen,
        setup_signal_handlers,
        format_mac,
        validate_mac
    )
    from src.logger import get_logger
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

# Initialize console and logger
console = Console()
logger = get_logger(__name__)

class NoiseMatrix:
    """Main application class - NoiseMatrix by Kkaxh1"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize NoiseMatrix"""
        try:
            self.config = load_config(config_path)
            self.interface_manager = None
            self.scanner = None
            self.attacker = None
            self.running = False
            self.interface = None
            self.saved_targets = self.load_saved_targets()
            self.scan_results = []  # Store last scan results
            self.initialized = False
            self._cleaned_up = False
            self._asked_monitor = False
            
            logger.info("NoiseMatrix initialized")
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            console.print(f"[red]Initialization failed: {e}[/red]")
            raise
        
    def load_saved_targets(self) -> List[Dict]:
        """Load previously saved targets"""
        targets = []
        targets_file = "targets/saved_targets.json"
        
        # Create targets directory if it doesn't exist
        os.makedirs("targets", exist_ok=True)
        
        if os.path.exists(targets_file):
            try:
                with open(targets_file, 'r') as f:
                    data = json.load(f)
                    targets = data.get('targets', [])
                logger.info(f"Loaded {len(targets)} saved targets")
            except Exception as e:
                logger.error(f"Error loading saved targets: {e}")
                
        return targets
        
    def save_target(self, target: Dict):
        """Save target to file"""
        targets_file = "targets/saved_targets.json"
        os.makedirs("targets", exist_ok=True)
        
        # Add timestamp
        target['saved_at'] = datetime.now().isoformat()
        
        # Check if target already exists
        for existing in self.saved_targets:
            if existing.get('bssid') == target.get('bssid'):
                # Update existing
                existing.update(target)
                break
        else:
            self.saved_targets.append(target)
            
        # Keep only last 50 targets
        if len(self.saved_targets) > 50:
            self.saved_targets = self.saved_targets[-50:]
            
        try:
            with open(targets_file, 'w') as f:
                json.dump({'targets': self.saved_targets}, f, indent=2)
            console.print("[green]✓ Target saved successfully[/green]")
            logger.info(f"Target saved: {target.get('bssid')}")
        except Exception as e:
            logger.error(f"Error saving target: {e}")
            
    def setup(self):
        """Initial setup and checks"""
        try:
            # Check if running as root
            if not check_root():
                console.print(Panel("[red]This tool must be run as root![/red]", border_style="red"))
                console.print("[yellow]Please run with: sudo python3 noisematrix.py[/yellow]")
                sys.exit(1)
                
            # Setup signal handlers
            setup_signal_handlers(self.cleanup)
            
            # Initialize interface manager
            self.interface_manager = InterfaceManager(self.config)
            
            # Show startup message
            self.show_startup_info()
            
            # Setup interface with monitor mode check
            self.interface = self.interface_manager.setup_interface()
            
            if not self.interface:
                console.print("[red]Failed to setup network interface![/red]")
                sys.exit(1)
                
            # Initialize scanner and attacker
            logger.info(f"Initializing scanner with interface: {self.interface}")
            self.scanner = WiFiScanner(self.interface, self.config)
            
            logger.info(f"Initializing attacker with interface: {self.interface}")
            self.attacker = DeauthAttacker(self.interface, self.config)
            
            # Verify initialization
            if self.scanner is None:
                console.print("[red]Failed to initialize scanner![/red]")
                sys.exit(1)
                
            if self.attacker is None:
                console.print("[red]Failed to initialize attacker![/red]")
                sys.exit(1)
                
            self.initialized = True
            logger.info("NoiseMatrix setup complete")
            
            # Show interface info
            self.show_interface_info()
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
            console.print(f"[red]Setup failed: {e}[/red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
    def show_startup_info(self):
        """Show startup information"""
        clear_screen()
        # Try to import banner from launcher
        try:
            import noisematrix
            if hasattr(noisematrix, 'print_banner'):
                noisematrix.print_banner()
        except:
            # Fallback banner
            console.print("[cyan]NoiseMatrix by Kkaxh1[/cyan]")
        
        info_panel = Panel(
            "[cyan]⚡ NoiseMatrix v1.0.0[/cyan]\n"
            "[magenta]Created by Kkaxh1[/magenta]\n"
            "[yellow]⚠️  FOR EDUCATIONAL USE ONLY[/yellow]\n"
            "[red]Unauthorized use is illegal![/red]",
            title="Welcome to NoiseMatrix",
            border_style="cyan",
            box=box.DOUBLE
        )
        console.print(info_panel)
        console.print()
        
    def show_interface_info(self):
        """Show interface information"""
        if not self.interface_manager or not self.interface:
            console.print("[red]Interface not initialized[/red]")
            return
            
        mode = self.interface_manager.get_current_mode(self.interface)
        
        if mode == "monitor":
            mode_style = "green"
            mode_text = "✓ MONITOR MODE"
        else:
            mode_style = "red"
            mode_text = "✗ MANAGED MODE"
            
        info_table = Table(show_header=False, box=box.ROUNDED)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")
        
        info_table.add_row("Interface", f"[bold]{self.interface}[/bold]")
        info_table.add_row("Mode", f"[{mode_style}]{mode_text}[/{mode_style}]")
        info_table.add_row("Status", "[green]Ready[/green]")
        
        console.print(Panel(info_table, title="Interface Status", border_style="blue"))
        console.print()
        
    def run(self):
        """Main application loop"""
        if not self.initialized:
            console.print("[red]Application not properly initialized![/red]")
            logger.error("Application not initialized")
            return
            
        logger.info("Starting main loop")
            
        while True:
            try:
                choice = self.show_main_menu()
                
                if choice == "1":
                    self.scan_networks()
                elif choice == "2":
                    self.show_saved_targets()
                elif choice == "3":
                    self.launch_attack()
                elif choice == "4":
                    self.show_attack_status()
                elif choice == "5":
                    self.quick_attack()
                elif choice == "6":
                    self.show_settings()
                elif choice == "7":
                    self.show_help()
                elif choice == "8":
                    self.show_about()
                elif choice == "9":
                    if self.confirm_exit():
                        self.cleanup()
                        break
                        
            except KeyboardInterrupt:
                if self.confirm_exit():
                    self.cleanup()
                    break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                console.print(f"[red]Error: {e}[/red]")
                time.sleep(2)
                
    def show_main_menu(self) -> str:
        """Display main menu with UI"""
        clear_screen()
        
        # Create header
        header = Panel(
            "[bold cyan]NoiseMatrix[/bold cyan] [dim]by Kkaxh1[/dim]\n"
            "[dim]Professional WiFi Security Testing Tool[/dim]",
            box=box.DOUBLE_EDGE
        )
        console.print(header)
        console.print()
        
        # Create menu items with icons
        menu_items = [
            ("1", "🔍", "Scan Networks", "Scan for available WiFi networks"),
            ("2", "📋", "Saved Targets", f"View {len(self.saved_targets)} saved targets"),
            ("3", "⚔️", "Launch Attack", "Start deauth attack on target"),
            ("4", "📊", "Attack Status", "View current attack statistics"),
            ("5", "⚡", "Quick Attack", "Quick attack with last target"),
            ("6", "⚙️", "Settings", "Configure tool parameters"),
            ("7", "📚", "Help", "View documentation and help"),
            ("8", "ℹ️", "About", "About NoiseMatrix"),
            ("9", "🚪", "Exit", "Exit and cleanup")
        ]
        
        # Create menu table
        menu_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        menu_table.add_column("Option", style="cyan", width=6)
        menu_table.add_column("Icon", width=4)
        menu_table.add_column("Function", style="bold yellow", width=20)
        menu_table.add_column("Description", style="dim white")
        
        for opt, icon, func, desc in menu_items:
            menu_table.add_row(opt, icon, func, desc)
            
        console.print(menu_table)
        console.print()
        
        # Show current interface status
        if self.interface and self.interface_manager:
            mode = self.interface_manager.get_current_mode(self.interface)
            status = f"[green]✓ {self.interface} ({mode})[/green]" if mode == "monitor" else f"[red]✗ {self.interface} ({mode})[/red]"
            console.print(f"[dim]Interface: {status}[/dim]")
            
        console.print()
        
        return Prompt.ask(
            "[cyan]Select option[/cyan]",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"]
        )
        
    def scan_networks(self):
        """Scan for WiFi networks with progress UI"""
        if not self.scanner:
            console.print("[red]Scanner not initialized![/red]")
            logger.error("Scanner not initialized")
            input("\nPress Enter to continue...")
            return
            
        clear_screen()
        
        # Show scanning panel
        scan_panel = Panel(
            "[yellow]📡 Scanning for WiFi Networks[/yellow]\n"
            "[dim]This may take up to 30 seconds...[/dim]",
            border_style="yellow"
        )
        console.print(scan_panel)
        console.print()
        
        # Perform scan with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Scanning networks...", total=30)
            
            # Start scan
            try:
                self.scan_results = self.scanner.scan(duration=30)
                
                # Update progress
                for i in range(30):
                    time.sleep(1)
                    if self.scanner and self.scanner.networks:
                        progress.update(task, advance=1, description=f"[cyan]Scanning... {len(self.scanner.networks)} networks found")
                    else:
                        progress.update(task, advance=1, description=f"[cyan]Scanning...")
            except Exception as e:
                logger.error(f"Scan error: {e}")
                console.print(f"[red]Scan failed: {e}[/red]")
                input("\nPress Enter to continue...")
                return
        
        # Show results
        self.display_scan_results()
        
    def display_scan_results(self):
        """Display scan results in a formatted table"""
        if not self.scanner or not self.scanner.networks:
            console.print("[red]No networks found![/red]")
            input("\nPress Enter to continue...")
            return
            
        # Create main results table
        main_table = Table(
            title="[bold green]Available Networks[/bold green]",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="green"
        )
        
        main_table.add_column("#", style="cyan", width=4)
        main_table.add_column("BSSID", style="bright_yellow", width=18)
        main_table.add_column("Channel", style="green", width=8, justify="center")
        main_table.add_column("Signal", style="blue", width=8, justify="center")
        main_table.add_column("Encryption", style="red", width=12)
        main_table.add_column("ESSID", style="white", width=30)
        
        # Sort by signal strength
        sorted_networks = sorted(
            self.scanner.networks,
            key=lambda x: int(x.get('signal', '0') or '0'),
            reverse=True
        )
        
        # Store for later use
        self.scan_results = sorted_networks
        
        for i, network in enumerate(sorted_networks[:15], 1):
            # Color code signal strength
            signal = network.get('signal', '0')
            try:
                signal_val = int(signal)
                if signal_val > -50:
                    signal_str = f"[green]{signal}dBm[/green]"
                elif signal_val > -70:
                    signal_str = f"[yellow]{signal}dBm[/yellow]"
                else:
                    signal_str = f"[red]{signal}dBm[/red]"
            except:
                signal_str = f"{signal}dBm"
                
            main_table.add_row(
                str(i),
                network.get('bssid', 'N/A'),
                str(network.get('channel', '?')),
                signal_str,
                network.get('encryption', 'N/A')[:10],
                network.get('essid', '[hidden]')[:28]
            )
            
        console.print(main_table)
        
        # Show summary
        total = len(self.scanner.networks)
        encrypted = sum(1 for n in self.scanner.networks if n.get('encryption') and n['encryption'] not in ['', 'OPN'])
        
        summary = Panel(
            f"[cyan]Total Networks: {total}[/cyan] | "
            f"[yellow]Encrypted: {encrypted}[/yellow] | "
            f"[green]Open: {total - encrypted}[/green]",
            border_style="blue"
        )
        console.print(summary)
        
        # Options after scan
        console.print()
        options = Columns([
            "[1] 💾 Save results",
            "[2] 🎯 Select target",
            "[3] ↩️  Main menu"
        ])
        console.print(options)
        console.print()
        
        choice = Prompt.ask(
            "[cyan]Choose option[/cyan]",
            choices=["1", "2", "3"]
        )
        
        if choice == "1":
            filename = self.scanner.save_results()
            if filename:
                console.print(f"[green]Results saved to {filename}[/green]")
            input("\nPress Enter to continue...")
            # Return to main menu instead of scanning again
            return
            
        elif choice == "2":
            target = self.select_target_from_list(sorted_networks)
            if target:
                self.configure_attack(target)
                
        # Choice "3" just returns to main menu
        
    def select_target_from_list(self, networks: List[Dict]) -> Optional[Dict]:
        """Select target from network list"""
        if not networks:
            return None
            
        # Display numbered list for selection
        console.print("\n[cyan]Select target by number:[/cyan]")
        
        for i, network in enumerate(networks[:15], 1):
            console.print(f"  {i}. {network.get('bssid')} - {network.get('essid', '[hidden]')} (CH {network.get('channel')})")
            
        console.print()
        
        try:
            choice = Prompt.ask(
                "[cyan]Enter target number[/cyan]",
                choices=[str(i) for i in range(1, min(16, len(networks)+1))]
            )
            return networks[int(choice)-1]
        except:
            return None
            
    def show_saved_targets(self):
        """Display saved targets"""
        clear_screen()
        
        if not self.saved_targets:
            console.print(Panel("[yellow]No saved targets found[/yellow]", border_style="yellow"))
            input("\nPress Enter to continue...")
            return
            
        table = Table(
            title="[bold cyan]Saved Targets[/bold cyan]",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        
        table.add_column("#", style="cyan", width=4)
        table.add_column("BSSID", style="yellow", width=18)
        table.add_column("Channel", width=8)
        table.add_column("ESSID", width=30)
        table.add_column("Saved", style="dim", width=20)
        
        for i, target in enumerate(self.saved_targets[-10:], 1):
            saved_time = target.get('saved_at', 'Unknown')[5:16] if 'saved_at' in target else 'Unknown'
            table.add_row(
                str(i),
                target.get('bssid', 'N/A'),
                str(target.get('channel', '?')),
                target.get('essid', 'Unknown')[:28],
                saved_time
            )
            
        console.print(table)
        console.print()
        
        if Confirm.ask("[cyan]Use a saved target for attack?[/cyan]"):
            choice = Prompt.ask(
                "Select target number",
                choices=[str(i) for i in range(1, min(11, len(self.saved_targets)+1))]
            )
            target = self.saved_targets[-10:][int(choice)-1]
            self.configure_attack(target)
        else:
            input("\nPress Enter to continue...")
            
    def launch_attack(self):
        """Launch attack from menu"""
        if not self.scan_results:
            console.print("[yellow]No scan results available. Please scan networks first.[/yellow]")
            if Confirm.ask("[cyan]Scan networks now?[/cyan]"):
                self.scan_networks()
            else:
                return
        
        target = self.select_target_from_list(self.scan_results)
        if target:
            self.configure_attack(target)
            
    def quick_attack(self):
        """Quick attack with last target"""
        if self.scan_results:
            # Use strongest network from last scan
            target = self.scan_results[0] if self.scan_results else None
            if target:
                console.print(f"[green]Using last scanned target: {target.get('essid')}[/green]")
                self.configure_attack(target)
                return
                
        if self.saved_targets:
            # Use last saved target
            target = self.saved_targets[-1]
            console.print(f"[green]Using last saved target: {target.get('essid')}[/green]")
            self.configure_attack(target)
            return
            
        console.print("[red]No targets available! Please scan or load saved targets.[/red]")
        input("\nPress Enter to continue...")
        
    def configure_attack(self, target: Dict):
        """Configure and launch attack"""
        clear_screen()
        
        # Attack configuration panel
        config_text = f"""
[red]⚠️  ATTACK CONFIGURATION[/red]

[yellow]Target Information:[/yellow]
  • BSSID: [cyan]{target['bssid']}[/cyan]
  • Channel: [cyan]{target.get('channel', '?')}[/cyan]
  • ESSID: [cyan]{target.get('essid', 'Unknown')}[/cyan]
  • Encryption: [cyan]{target.get('encryption', 'Unknown')}[/cyan]
        """
        
        console.print(Panel(config_text, border_style="red"))
        
        # Attack parameters
        console.print("[yellow]Attack Parameters:[/yellow]")
        
        intensity = Prompt.ask(
            "  Attack intensity",
            choices=["low", "medium", "high"],
            default="medium"
        )
        
        duration = Prompt.ask(
            "  Attack duration in seconds (0 for unlimited)",
            default="0"
        )
        
        packet_rates = {"low": 300, "medium": 600, "high": 1000}
        target['packet_rate'] = packet_rates[intensity]
        target['duration'] = int(duration) if duration.isdigit() else 0
        
        # Save option
        if Confirm.ask("[cyan]Save this target for future use?[/cyan]"):
            self.save_target(target)
            
        # Final warning
        console.print()
        warning = Panel(
            "[red]⚠️  WARNING: This attack will disrupt the target network!\n"
            "Only use on networks you own or have permission to test!\n"
            "This may be illegal in your jurisdiction.[/red]",
            border_style="red"
        )
        console.print(warning)
        console.print()
        
        if Confirm.ask("[red]Do you want to proceed with the attack?[/red]"):
            self.execute_attack(target)
            
    def execute_attack(self, target: Dict):
        """Execute the attack with monitoring"""
        clear_screen()
        
        # Start attack
        try:
            self.attacker.start_attack(
                target_bssid=target['bssid'],
                channel=int(target.get('channel', 1)),
                packet_rate=target.get('packet_rate', 600)
            )
            
            # Attack header
            header = Panel(
                f"[red]⚔️  ATTACK IN PROGRESS[/red]\n"
                f"Target: {target['bssid']} | Channel: {target.get('channel', '?')}\n"
                f"[dim]Press Ctrl+C to stop[/dim]",
                border_style="red"
            )
            console.print(header)
            console.print()
            
            # Monitor attack
            start_time = time.time()
            duration = target.get('duration', 0)
            
            try:
                while self.attacker.is_running():
                    # Calculate elapsed time
                    elapsed = int(time.time() - start_time)
                    
                    # Check duration limit
                    if duration > 0 and elapsed >= duration:
                        console.print("\n[yellow]Attack duration reached[/yellow]")
                        break
                    
                    # Get status
                    status = self.attacker.get_status()
                    
                    # Create status display
                    status_table = Table(show_header=False, box=box.SIMPLE)
                    status_table.add_column("Metric", style="cyan")
                    status_table.add_column("Value", style="white")
                    
                    status_table.add_row("Packets Sent", f"[yellow]{status['packets_sent']:,}[/yellow]")
                    status_table.add_row("Active Threads", f"[green]{status['processes']}[/green]")
                    status_table.add_row("Elapsed Time", f"[blue]{elapsed}s[/blue]")
                    
                    if duration > 0:
                        remaining = duration - elapsed
                        status_table.add_row("Time Remaining", f"[blue]{remaining}s[/blue]")
                    
                    # Clear and update display
                    console.clear()
                    console.print(header)
                    console.print()
                    console.print(status_table)
                    console.print()
                    
                    # Show packet rate graph
                    self.show_packet_graph(status['packets_sent'], elapsed)
                    
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Attack interrupted by user[/yellow]")
                
            finally:
                # Always stop the attack properly
                self.attacker.stop_attack()
                
            # Show final statistics
            self.show_attack_summary(target, int(time.time() - start_time))
            
        except Exception as e:
            logger.error(f"Attack error: {e}")
            console.print(f"[red]Attack failed: {e}[/red]")
            
        input("\nPress Enter to continue...")
        
    def show_packet_graph(self, packets: int, elapsed: int):
        """Show simple packet rate graph"""
        # Calculate rate (packets per second)
        rate = packets // max(1, elapsed)
        
        # Create bar graph
        max_rate = 1000
        bar_length = min(50, int((rate / max_rate) * 50))
        bar = "█" * bar_length
        
        # Color code based on rate
        if rate < 300:
            color = "green"
        elif rate < 600:
            color = "yellow"
        else:
            color = "red"
            
        graph = f"[{color}]{bar}[/{color}]"
        console.print(f"Packet Rate: {graph} {rate}/s")
        
    def show_attack_summary(self, target: Dict, elapsed: int):
        """Show attack summary"""
        summary = Panel(
            f"[green]✓ Attack Completed[/green]\n\n"
            f"Target: {target['bssid']}\n"
            f"Duration: {elapsed} seconds\n"
            f"Total Packets: {self.attacker.packets_sent:,}\n"
            f"Average Rate: {self.attacker.packets_sent // max(1, elapsed)} packets/s",
            title="Attack Summary",
            border_style="green"
        )
        console.print(summary)
        
    def show_attack_status(self):
        """Show current attack status"""
        clear_screen()
        
        if not self.attacker or not self.attacker.is_running():
            console.print(Panel("[yellow]No active attack[/yellow]", border_style="yellow"))
            input("\nPress Enter to continue...")
            return
            
        status = self.attacker.get_status()
        
        status_panel = Panel(
            f"[red]⚔️  ACTIVE ATTACK[/red]\n\n"
            f"Target: [cyan]{status['target']}[/cyan]\n"
            f"Channel: [cyan]{status['channel']}[/cyan]\n"
            f"Packets Sent: [yellow]{status['packets_sent']:,}[/yellow]\n"
            f"Active Threads: [green]{status['processes']}[/green]",
            border_style="red"
        )
        console.print(status_panel)
        
        if Confirm.ask("[red]Stop the current attack?[/red]"):
            self.attacker.stop_attack()
            console.print("[green]Attack stopped[/green]")
            
        input("\nPress Enter to continue...")
        
    def show_settings(self):
        """Display and modify settings"""
        clear_screen()
        
        settings_table = Table(
            title="[bold cyan]Current Settings[/bold cyan]",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        
        settings_table.add_column("Setting", style="yellow")
        settings_table.add_column("Value", style="green")
        settings_table.add_column("Description", style="dim white")
        
        # Add settings with descriptions
        settings = [
            ("monitor_mode", self.config.get('monitor_mode', 'true'), "Auto-enable monitor mode"),
            ("scan_timeout", self.config.get('scan_timeout', '30'), "Scan duration in seconds"),
            ("packet_rate", self.config.get('packet_rate', '1000'), "Default packet rate"),
            ("log_level", self.config.get('log_level', 'INFO'), "Logging verbosity"),
        ]
        
        for name, value, desc in settings:
            settings_table.add_row(name, value, desc)
            
        console.print(settings_table)
        console.print()
        
        if Confirm.ask("[cyan]Reset to default settings?[/cyan]"):
            self.config = load_config(force_default=True)
            console.print("[green]Settings reset to default[/green]")
            
        input("\nPress Enter to continue...")
        
    def show_help(self):
        """Display help information"""
        clear_screen()
        
        help_text = """
[bold cyan]NoiseMatrix Help - Created by Kkaxh1[/bold cyan]

[yellow]📖 QUICK START GUIDE:[/yellow]

1. [green]Scan Networks[/green] - Find available WiFi networks
2. [green]Select Target[/green] - Choose a network to test
3. [green]Configure Attack[/green] - Set intensity and duration
4. [green]Monitor Attack[/green] - Watch real-time statistics

[yellow]⚡ ATTACK INTENSITIES:[/yellow]
• [dim]Low (300 pkts/s)[/dim] - Less noticeable, good for testing
• [yellow]Medium (600 pkts/s)[/yellow] - Balanced performance
• [red]High (1000 pkts/s)[/red] - Maximum disruption

[yellow]🎯 TARGET SELECTION:[/yellow]
• From live scan results
• From saved targets list
• Quick attack with last target

[yellow]⚠️  LEGAL WARNING:[/yellow]
[red]This tool is for EDUCATIONAL PURPOSES ONLY!
Using it against networks you don't own is ILLEGAL!
Always obtain written permission before testing.[/red]

[yellow]⌨️  KEYBOARD SHORTCUTS:[/yellow]
• Ctrl+C - Stop current operation / Graceful exit
• Enter - Confirm selection

[yellow]📁 CONFIGURATION:[/yellow]
Edit [cyan]config/default.config[/cyan] to customize settings

[yellow]📊 LOGS & DATA:[/yellow]
• Scan results: [cyan]logs/scan_*.json[/cyan]
• Saved targets: [cyan]targets/saved_targets.json[/cyan]
• Attack logs: [cyan]logs/noisematrix.log[/cyan]
        """
        
        console.print(Panel(help_text, border_style="cyan", title="Help", title_align="left"))
        input("\nPress Enter to continue...")
        
    def show_about(self):
        """Show about information"""
        clear_screen()
        
        about_text = f"""
[bold cyan]NoiseMatrix v1.0.0[/bold cyan]
[magenta]Created by Kkaxh1[/magenta]

[yellow]Description:[/yellow]
Professional WiFi security testing tool for educational purposes.
Perform deauthentication attacks to test network security.

[yellow]Features:[/yellow]
• Network scanning (2.4GHz & 5GHz)
• Deauthentication attacks
• Target management
• Real-time attack monitoring
• Packet rate visualization
• Saved targets database

[yellow]GitHub:[/yellow] https://github.com/Kkaxh1/NoiseMatrix
[yellow]License:[/yellow] MIT (Educational Use Only)

[red]Remember: With great power comes great responsibility![/red]
        """
        
        console.print(Panel(about_text, border_style="cyan", title="About NoiseMatrix", title_align="left"))
        input("\nPress Enter to continue...")
        
    def confirm_exit(self) -> bool:
        """Confirm exit with monitor mode warning"""
        if self.interface_manager and self.interface_manager.interface:
            mode = self.interface_manager.get_current_mode(self.interface_manager.interface)
            if mode == "monitor":
                console.print()
                warning = Panel(
                    "[yellow]⚠️  Interface is still in MONITOR MODE[/yellow]\n\n"
                    "Do you want to disable monitor mode before exiting?\n"
                    "This will restore normal WiFi functionality.",
                    border_style="yellow"
                )
                console.print(warning)
                
                if Confirm.ask("[cyan]Disable monitor mode?[/cyan]", default=True):
                    return True
                else:
                    console.print("[red]Warning: Interface will remain in monitor mode[/red]")
                    time.sleep(2)
                    
        return Confirm.ask("[cyan]Are you sure you want to exit?[/cyan]")
        
    def cleanup(self):
        """Cleanup before exit"""
        # Prevent multiple cleanup calls
        if hasattr(self, '_cleaned_up') and self._cleaned_up:
            return
            
        console.print("\n[yellow]Cleaning up...[/yellow]")
        
        # Stop any ongoing attack
        if self.attacker:
            try:
                self.attacker.stop_attack()
            except Exception as e:
                logger.error(f"Error stopping attack: {e}")
        
        # Handle monitor mode
        if self.interface_manager and self.interface_manager.interface:
            mode = self.interface_manager.get_current_mode(self.interface_manager.interface)
            if mode == "monitor":
                console.print()
                # Only ask if we haven't already asked
                if not hasattr(self, '_asked_monitor') or not self._asked_monitor:
                    self._asked_monitor = True
                    if Confirm.ask("[yellow]Disable monitor mode before exit?[/yellow]", default=True):
                        try:
                            self.interface_manager.disable_monitor_mode()
                            console.print("[green]✓ Monitor mode disabled[/green]")
                        except Exception as e:
                            logger.error(f"Error disabling monitor mode: {e}")
                    else:
                        console.print("[red]Warning: Interface left in monitor mode[/red]")
                else:
                    # Already asked, just disable
                    try:
                        self.interface_manager.disable_monitor_mode()
                    except:
                        pass
            else:
                try:
                    self.interface_manager.cleanup()
                except Exception as e:
                    logger.error(f"Error during interface cleanup: {e}")
        
        logger.info("NoiseMatrix shutdown complete")
        self._cleaned_up = True
        
        # Final message
        console.print()
        goodbye = Panel(
            "[green]Thank you for using NoiseMatrix![/green]\n"
            "[magenta]Created by Kkaxh1[/magenta]\n"
            "[dim]Remember: With great power comes great responsibility[/dim]",
            border_style="green"
        )
        console.print(goodbye)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="NoiseMatrix - WiFi Security Tool")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default=None
    )
    parser.add_argument(
        "-i", "--interface",
        help="Network interface to use"
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="NoiseMatrix v1.0.0 by Kkaxh1"
    )
    
    args = parser.parse_args()
    
    # Create and run application
    try:
        app = NoiseMatrix(args.config)
        app.setup()
        app.run()
    except KeyboardInterrupt:
        print(f"\n[yellow]Exiting...[/yellow]")
        sys.exit(0)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Fatal error: {e}")
        console.print(f"[red]Fatal error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()