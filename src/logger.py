"""
Logging configuration module
"""

import logging
import logging.config
import os
from typing import Optional

def setup_logging(config_path: Optional[str] = None):
    """Setup logging configuration"""
    if not config_path:
        config_path = "config/logging.conf"
        
    if os.path.exists(config_path):
        logging.config.fileConfig(config_path)
    else:
        # Basic logging if config not found
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)