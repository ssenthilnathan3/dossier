"""
Simple test for configuration manager
"""

import tempfile
import os
from pathlib import Path
from .manager import ConfigManager
from ..models.config import DoctypeConfig


def test_config_manager():
    """Test basic configuration manager functionality"""
    
    # Create a temporary config file path (file doesn't exist yet)
    import tempfile
    temp_dir = tempfile.mkdtemp()
    config_path = os.path.join(temp_dir, "test_config.json")
    
    try:
        # Initialize config manager
        manager = ConfigManager(config_path)
        
        # Test default configs are created
        assert len(manager.list_doctypes()) > 0
        print(f"✓ Default configs created: {manager.list_doctypes()}")
        
        # Test getting a config
        user_config = manager.get_config("User")
        assert user_config is not None
        assert user_config.doctype == "User"
        print(f"✓ Retrieved User config: {user_config.fields}")
        
        # Test adding a new config
        new_config = DoctypeConfig(
            doctype="Test Document",
            enabled=True,
            fields=["title", "content"],
            filters={"status": "Published"},
            chunk_size=800,
            chunk_overlap=100
        )
        manager.add_config(new_config)
        
        # Verify it was added
        retrieved_config = manager.get_config("Test Document")
        assert retrieved_config is not None
        assert retrieved_config.chunk_size == 800
        print("✓ Added and retrieved new config")
        
        # Test enabled configs
        enabled_configs = manager.get_enabled_configs()
        assert len(enabled_configs) > 0
        print(f"✓ Found {len(enabled_configs)} enabled configs")
        
        # Test is_enabled
        assert manager.is_enabled("User") == True
        assert manager.is_enabled("NonExistent") == False
        print("✓ is_enabled works correctly")
        
        print("All tests passed!")
        
    finally:
        # Clean up
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_config_manager()