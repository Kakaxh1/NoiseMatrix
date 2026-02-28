"""
Configuration management
"""

import os
import configparser
from typing import Any

class ConfigManager:
    """Manage application configuration"""
    
    def __init__(self, config_path=None):
        self.config = configparser.ConfigParser()
        
        # Try multiple config locations
        config_locations = [
            config_path,
            "config/default.config",
            "/etc/wifi-jammer/default.config",
            os.path.expanduser("~/.config/wifi-jammer/config")
        ]
        
        loaded = False
        for location in config_locations:
            if location and os.path.exists(location):
                self.config.read(location)
                loaded = True
                break
                
        if not loaded:
            # Create default config
            self.config['DEFAULT'] = {
                'monitor_mode': 'true',
                'scan_timeout': '30',
                'packet_rate': '1000',
                'log_level': 'INFO'
            }
            
    def get(self, key, fallback=None):
        """Get config value"""
        try:
            return self.config['DEFAULT'].get(key, fallback)
        except:
            return fallback
            
    def getboolean(self, key, fallback=False):
        """Get boolean config value"""
        try:
            return self.config['DEFAULT'].getboolean(key, fallback)
        except:
            return fallback
            
    def getint(self, key, fallback=0):
        """Get integer config value"""
        try:
            return self.config['DEFAULT'].getint(key, fallback)
        except:
            return fallback