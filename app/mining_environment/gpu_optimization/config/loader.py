"""
Configuration Loader
====================
Load and validate configuration files
Tải và xác thực các file cấu hình
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfigSchema:
    """Configuration schema definition.
    
    Định nghĩa schema cấu hình.
    """
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, type]
    
    def validate(self, config: Dict[str, Any]) -> bool:
        """Validate config against schema.
        
        Xác thực cấu hình theo schema.
        """
        # Check required fields - kiểm tra trường bắt buộc
        for field in self.required_fields:
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False
                
        # Check field types - kiểm tra kiểu dữ liệu
        for field, expected_type in self.field_types.items():
            if field in config and not isinstance(config[field], expected_type):
                logger.error(f"Invalid type for {field}: expected {expected_type}, got {type(config[field])}")
                return False
                
        return True


class ConfigLoader:
    """Configuration loader and validator.
    
    Trình tải và xác thực cấu hình.
    """
    
    # Default config paths - đường dẫn cấu hình mặc định
    DEFAULT_CONFIG_DIR = Path(__file__).parent
    DEFAULT_CONFIG_FILE = "default_config.yaml"
    
    # Config schemas - schema cấu hình
    GPU_OPTIMIZATION_SCHEMA = ConfigSchema(
        required_fields=['enabled', 'strategies', 'target_processes'],
        optional_fields=['monitoring_interval', 'log_level', 'max_workers'],
        field_types={
            'enabled': bool,
            'strategies': list,
            'target_processes': list,
            'monitoring_interval': (int, float),
            'log_level': str,
            'max_workers': int
        }
    )
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config loader.
        
        Khởi tạo trình tải cấu hình.
        
        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self._cache: Dict[str, Any] = {}
        self.logger = logger
        
    def load_yaml(self, filepath: Path) -> Dict[str, Any]:
        """Load YAML configuration file.
        
        Tải file cấu hình YAML.
        
        Args:
            filepath: Path to YAML file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            self.logger.info(f"Loaded config from {filepath}")
            return config
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {filepath}")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML: {e}")
            return {}
            
    def load_json(self, filepath: Path) -> Dict[str, Any]:
        """Load JSON configuration file.
        
        Tải file cấu hình JSON.
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Loaded config from {filepath}")
            return config
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {filepath}")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON: {e}")
            return {}
            
    def load_config(self, name: str = "default") -> Dict[str, Any]:
        """Load configuration by name.
        
        Tải cấu hình theo tên.
        
        Args:
            name: Configuration name
            
        Returns:
            Configuration dictionary
        """
        # Check cache first - kiểm tra cache trước
        if name in self._cache:
            return self._cache[name]
            
        # Try different file formats - thử các định dạng file khác nhau
        for ext in ['.yaml', '.yml', '.json']:
            filepath = self.config_dir / f"{name}_config{ext}"
            if filepath.exists():
                if ext in ['.yaml', '.yml']:
                    config = self.load_yaml(filepath)
                else:
                    config = self.load_json(filepath)
                    
                # Cache loaded config - lưu cache cấu hình
                self._cache[name] = config
                return config
                
        # Return empty config if not found - trả về cấu hình rỗng nếu không tìm thấy
        self.logger.warning(f"No config found for: {name}")
        return {}
        
    def validate_config(self, config: Dict[str, Any], schema: Optional[ConfigSchema] = None) -> bool:
        """Validate configuration against schema.
        
        Xác thực cấu hình theo schema.
        
        Args:
            config: Configuration to validate
            schema: Schema to validate against
            
        Returns:
            True if valid, False otherwise
        """
        if schema is None:
            schema = self.GPU_OPTIMIZATION_SCHEMA
            
        return schema.validate(config)
        
    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple configurations.
        
        Hợp nhất nhiều cấu hình.
        
        Args:
            *configs: Configurations to merge
            
        Returns:
            Merged configuration
        """
        result = {}
        for config in configs:
            result.update(config)
        return result
        
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration.
        
        Lấy cấu hình mặc định.
        
        Returns:
            Default configuration
        """
        return {
            'enabled': True,
            'strategies': ['power_optimization', 'memory_optimization'],
            'target_processes': [],
            'monitoring_interval': 60,
            'log_level': 'INFO',
            'max_workers': 4,
            'gpu_mapping': {
                0: ['power', 'memory'],
                1: ['compute', 'thermal']
            }
        }
        
    def save_config(self, config: Dict[str, Any], name: str, format: str = 'yaml') -> bool:
        """Save configuration to file.
        
        Lưu cấu hình vào file.
        
        Args:
            config: Configuration to save
            name: Configuration name
            format: File format (yaml or json)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if format == 'yaml':
                filepath = self.config_dir / f"{name}_config.yaml"
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, default_flow_style=False)
            elif format == 'json':
                filepath = self.config_dir / f"{name}_config.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return False
                
            self.logger.info(f"Saved config to {filepath}")
            # Update cache - cập nhật cache
            self._cache[name] = config
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False


# Export ConfigLoader
__all__ = ['ConfigLoader', 'ConfigSchema']
