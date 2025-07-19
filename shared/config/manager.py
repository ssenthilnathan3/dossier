"""
Configuration management system for the Dossier RAG System
"""

import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from ..models.config import DoctypeConfig


class ConfigManager:
    """Manages configuration for doctypes and system settings"""
    
    def __init__(self, config_path: str = "config/doctypes.json"):
        self.config_path = Path(config_path)
        self._configs: Dict[str, DoctypeConfig] = {}
        self._load_configs()
    
    def _load_configs(self) -> None:
        """Load configurations from file"""
        if not self.config_path.exists():
            self._create_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            for doctype, config_data in data.items():
                self._configs[doctype] = DoctypeConfig(**config_data)
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    def _create_default_config(self) -> None:
        """Create default configuration file"""
        default_configs = {
            "User": {
                "doctype": "User",
                "enabled": True,
                "fields": ["full_name", "bio", "email"],
                "filters": {"enabled": 1},
                "chunkSize": 500,
                "chunkOverlap": 50
            },
            "Blog Post": {
                "doctype": "Blog Post",
                "enabled": True,
                "fields": ["title", "content", "meta_description"],
                "filters": {"published": 1},
                "chunkSize": 1000,
                "chunkOverlap": 200
            }
        }
        
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            json.dump(default_configs, f, indent=2, default=str)
        
        # Load the default configs
        for doctype, config_data in default_configs.items():
            self._configs[doctype] = DoctypeConfig(**config_data)
    
    def get_config(self, doctype: str) -> Optional[DoctypeConfig]:
        """Get configuration for a specific doctype"""
        return self._configs.get(doctype)
    
    def get_enabled_configs(self) -> List[DoctypeConfig]:
        """Get all enabled doctype configurations"""
        return [config for config in self._configs.values() if config.enabled]
    
    def add_config(self, config: DoctypeConfig) -> None:
        """Add or update a doctype configuration"""
        self._configs[config.doctype] = config
        self._save_configs()
    
    def remove_config(self, doctype: str) -> bool:
        """Remove a doctype configuration"""
        if doctype in self._configs:
            del self._configs[doctype]
            self._save_configs()
            return True
        return False
    
    def _save_configs(self) -> None:
        """Save configurations to file"""
        data = {}
        for doctype, config in self._configs.items():
            data[doctype] = config.dict(by_alias=True)
        
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def reload(self) -> None:
        """Reload configurations from file"""
        self._configs.clear()
        self._load_configs()
    
    def list_doctypes(self) -> List[str]:
        """List all configured doctypes"""
        return list(self._configs.keys())
    
    def is_enabled(self, doctype: str) -> bool:
        """Check if a doctype is enabled"""
        config = self.get_config(doctype)
        return config.enabled if config else False