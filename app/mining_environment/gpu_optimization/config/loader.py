"""
Configuration Loader - Production Ready
========================================
Advanced configuration management with hierarchical override
Quản lý cấu hình nâng cao với ghi đè phân cấp

Features:
- Singleton pattern (mẫu đơn thể) - truy cập toàn cục
- Environment variable override (ghi đè biến môi trường) - GPU_OPT_* prefix
- Schema validation (kiểm tra lược đồ) - type safety & constraints
- Hot reload (tải lại nóng) - runtime configuration updates
- Profile support (hỗ trợ profile) - dev/staging/production
- Caching (bộ nhớ đệm) - performance optimization
"""

import os
import re
import json
import yaml
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, TypeVar, Type
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import hashlib
from copy import deepcopy

# Setup logger với format chuẩn
logger = logging.getLogger(__name__)


# Configuration profiles enum
class ConfigProfile(Enum):
    """Configuration profiles (các profile cấu hình)"""
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    CUSTOM = "custom"


@dataclass
class ConfigValidationResult:
    """
    Configuration validation result.
    Kết quả kiểm tra cấu hình.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, message: str):
        """Add validation error (thêm lỗi kiểm tra)"""
        self.errors.append(message)
        self.is_valid = False
        
    def add_warning(self, message: str):
        """Add validation warning (thêm cảnh báo kiểm tra)"""
        self.warnings.append(message)


@dataclass 
class ConfigSchema:
    """
    Advanced configuration schema with constraints.
    Schema cấu hình nâng cao với ràng buộc.
    """
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, type] = field(default_factory=dict)
    field_constraints: Dict[str, Any] = field(default_factory=dict)
    nested_schemas: Dict[str, 'ConfigSchema'] = field(default_factory=dict)
    
    def validate(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """
        Validate config against schema with detailed results.
        Xác thực cấu hình theo schema với kết quả chi tiết.
        """
        result = ConfigValidationResult(is_valid=True)
        
        # Check required fields - kiểm tra trường bắt buộc
        for field in self.required_fields:
            if not self._check_nested_field(config, field):
                result.add_error(f"Missing required field: {field}")
                
        # Check field types - kiểm tra kiểu dữ liệu
        for field_path, expected_type in self.field_types.items():
            value = self._get_nested_value(config, field_path)
            if value is not None and not isinstance(value, expected_type):
                result.add_error(
                    f"Wrong type for {field_path}: expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
                
        # Check constraints - kiểm tra ràng buộc
        for field_path, constraint in self.field_constraints.items():
            value = self._get_nested_value(config, field_path)
            if value is not None:
                # Skip constraint check if type is wrong (already reported above)
                expected_type = self.field_types.get(field_path)
                if expected_type and not isinstance(value, expected_type):
                    continue  # Type error already reported
                    
                if not self._validate_constraint(value, constraint):
                    result.add_error(
                        f"Constraint violation for {field_path}: {constraint}"
                    )
                    
        # Validate nested schemas - kiểm tra schema lồng nhau
        for field_path, nested_schema in self.nested_schemas.items():
            nested_config = self._get_nested_value(config, field_path)
            if nested_config:
                nested_result = nested_schema.validate(nested_config)
                if not nested_result.is_valid:
                    for error in nested_result.errors:
                        result.add_error(f"{field_path}.{error}")
                    for warning in nested_result.warnings:
                        result.add_warning(f"{field_path}.{warning}")
                        
        return result
    
    def _check_nested_field(self, config: Dict, field_path: str) -> bool:
        """Check if nested field exists (kiểm tra trường lồng nhau tồn tại)"""
        parts = field_path.split('.')
        current = config
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return True
    
    def _get_nested_value(self, config: Dict, field_path: str) -> Any:
        """Get nested field value (lấy giá trị trường lồng nhau)"""
        parts = field_path.split('.')
        current = config
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
    
    def _validate_constraint(self, value: Any, constraint: Any) -> bool:
        """Validate value against constraint (kiểm tra giá trị theo ràng buộc)"""
        if isinstance(constraint, dict):
            if 'min' in constraint and value < constraint['min']:
                return False
            if 'max' in constraint and value > constraint['max']:
                return False
            if 'in' in constraint and value not in constraint['in']:
                return False
            if 'regex' in constraint:
                import re
                if not re.match(constraint['regex'], str(value)):
                    return False
        elif callable(constraint):
            return constraint(value)
        return True


class ConfigLoader:
    """
    Advanced Configuration Loader with Production Features.
    Trình tải cấu hình nâng cao với tính năng production.
    
    Features:
    - Singleton pattern for global access
    - Hierarchical config override: defaults → file → env → runtime
    - Hot reload capability 
    - Profile-based configuration
    - Thread-safe operations
    """
    
    # Singleton instance
    _instance = None
    _lock = threading.Lock()
    
    # Configuration constants
    DEFAULT_CONFIG_DIR = Path(__file__).parent
    DEFAULT_CONFIG_FILE = "default.yaml"
    ENV_PREFIX = "GPU_OPT_"
    CACHE_TTL = 300  # 5 minutes cache TTL
    
    # Define comprehensive schema - schema toàn diện
    MAIN_SCHEMA = ConfigSchema(
        required_fields=[
            'system.enabled',
            'metadata.version'
        ],
        field_types={
            'system.enabled': bool,
            'system.debug_mode': bool,
            'system.log_level': str,
            'orchestrator.max_workers': int,
            'orchestrator.min_workers': int,
            'orchestrator.scheduling_interval': (int, float),
            'monitoring.enabled': bool,
            'monitoring.sampling_rate': (int, float),
            'monitoring.buffer_size': int,
            'strategies.default': str,
            'strategies.available': list,
            'resource_control.enabled': bool,
            'coordination.enabled': bool,
            'coordination.max_concurrent_processes': int,
            'profiling.enabled': bool,
            'parallel_execution.enabled': bool,
            'parallel_execution.max_parallel_tasks': int
        },
        field_constraints={
            'system.log_level': {'in': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
            'orchestrator.max_workers': {'min': 1, 'max': 32},
            'orchestrator.scheduling_interval': {'min': 10, 'max': 10000},
            'monitoring.sampling_rate': {'min': 1, 'max': 10000},
            'monitoring.buffer_size': {'min': 64, 'max': 65536},
            'coordination.max_concurrent_processes': {'min': 1, 'max': 128},
            'parallel_execution.max_parallel_tasks': {'min': 1, 'max': 256}
        }
    )
    
    def __new__(cls, *args, **kwargs):
        """
        Implement singleton pattern.
        Triển khai mẫu singleton.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, 
                 config_dir: Optional[Path] = None,
                 profile: Optional[str] = None,
                 auto_reload: bool = False):
        """
        Initialize config loader (only runs once due to singleton).
        Khởi tạo trình tải cấu hình (chỉ chạy một lần do singleton).
        
        Args:
            config_dir: Configuration directory path
            profile: Configuration profile (dev/staging/production)
            auto_reload: Enable automatic config reloading
        """
        if self._initialized:
            return
            
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.profile = profile or os.getenv('GPU_OPT_PROFILE', 'production')
        self.auto_reload = auto_reload
        
        # Internal state - trạng thái nội bộ
        self._cache: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}
        self._file_checksums: Dict[str, str] = {}
        self._last_reload: Optional[datetime] = None
        self._reload_lock = threading.RLock()
        self._watchers: List[callable] = []
        
        # Load initial configuration
        self._config = self.load_config()
        self._initialized = True
        
        logger.info(f"ConfigLoader initialized with profile: {self.profile}")
        
    def load_yaml(self, filepath: Path) -> Dict[str, Any]:
        """
        Load YAML configuration file with caching.
        Tải file cấu hình YAML với bộ nhớ đệm.
        
        Args:
            filepath: Path to YAML file
            
        Returns:
            Configuration dictionary
        """
        try:
            # Check cache với checksum
            file_checksum = self._calculate_checksum(filepath)
            cache_key = f"yaml_{filepath}"
            
            if cache_key in self._cache:
                cached_checksum, cached_config = self._cache[cache_key]
                if cached_checksum == file_checksum:
                    logger.debug(f"Using cached config for {filepath}")
                    return deepcopy(cached_config)
            
            # Load fresh config
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                
            # Update cache
            self._cache[cache_key] = (file_checksum, config)
            self._file_checksums[str(filepath)] = file_checksum
            
            logger.info(f"✅ Loaded YAML config from {filepath}")
            return deepcopy(config)
            
        except FileNotFoundError:
            logger.warning(f"⚠️ Config file not found: {filepath}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"❌ Error parsing YAML: {e}")
            return {}
            
    def _calculate_checksum(self, filepath: Path) -> str:
        """
        Calculate file checksum for cache validation.
        Tính checksum file để xác thực cache.
        """
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides with GPU_OPT_ prefix.
        Áp dụng ghi đè biến môi trường với tiền tố GPU_OPT_.
        
        Example:
            GPU_OPT_SYSTEM_ENABLED=false
            GPU_OPT_ORCHESTRATOR_MAX_WORKERS=8
            GPU_OPT_MONITORING_SAMPLING_RATE=2000
        """
        env_overrides = {}
        
        # Scan environment variables - quét biến môi trường
        for key, value in os.environ.items():
            if key.startswith(self.ENV_PREFIX):
                # Remove prefix and convert to config path
                # E.g., GPU_OPT_SYSTEM_DEBUG_MODE -> system.debug_mode
                # First part is top level, rest uses underscores as field names
                key_parts = key[len(self.ENV_PREFIX):].lower().split('_', 1)
                if len(key_parts) == 1:
                    config_key = key_parts[0]
                else:
                    # Keep underscores in field names
                    config_key = f"{key_parts[0]}.{key_parts[1]}"
                
                # Parse value type - phân tích kiểu giá trị
                parsed_value = self._parse_env_value(value)
                
                # Store for override
                env_overrides[config_key] = parsed_value
                logger.debug(f"Environment override: {config_key} = {parsed_value}")
        
        # Apply overrides to config - áp dụng ghi đè vào config
        for key_path, value in env_overrides.items():
            self._set_nested_value(config, key_path, value)
            
        if env_overrides:
            logger.info(f"Applied {len(env_overrides)} environment variable overrides")
            
        return config
    
    def _parse_env_value(self, value: str) -> Any:
        """
        Parse environment variable value to appropriate type.
        Phân tích giá trị biến môi trường thành kiểu phù hợp.
        """
        # Try boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
            
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
            
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
            
        # Try JSON (for lists/dicts)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
            
        # Return as string
        return value
    
    def _set_nested_value(self, config: Dict, key_path: str, value: Any):
        """
        Set nested value in config dictionary.
        Đặt giá trị lồng nhau trong dictionary config.
        """
        parts = key_path.split('.')
        current = config
        
        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        # Set final value
        current[parts[-1]] = value
            
    def load_config(self, name: str = "default", force_reload: bool = False) -> Dict[str, Any]:
        """
        Load configuration with hierarchical override.
        Tải cấu hình với ghi đè phân cấp.
        
        Override hierarchy (thứ tự ghi đè):
        1. Default config (cấu hình mặc định)
        2. Profile-specific config (cấu hình theo profile) 
        3. Environment variables (biến môi trường)
        4. Runtime overrides (ghi đè runtime)
        
        Args:
            name: Configuration name
            force_reload: Force reload from disk
            
        Returns:
            Merged configuration dictionary
        """
        with self._reload_lock:
            # Check if reload needed - kiểm tra cần reload không
            if not force_reload and self._config and not self._should_reload():
                return deepcopy(self._config)
            
            logger.info(f"🔄 Loading configuration: {name} (profile: {self.profile})")
            
            # 1. Load default config - tải config mặc định
            default_path = self.config_dir / self.DEFAULT_CONFIG_FILE
            base_config = self.load_yaml(default_path) if default_path.exists() else {}
            
            # 2. Load profile-specific config if exists - tải config theo profile
            profile_path = self.config_dir / f"{self.profile}.yaml"
            if profile_path.exists():
                profile_config = self.load_yaml(profile_path)
                base_config = self._deep_merge(base_config, profile_config)
                logger.info(f"Applied profile config: {self.profile}")
            
            # 3. Apply environment variable overrides - áp dụng ghi đè từ env
            base_config = self._apply_env_overrides(base_config)
            
            # 4. Validate configuration - kiểm tra cấu hình
            validation_result = self.validate_config(base_config)
            if not validation_result.is_valid:
                logger.error(f"❌ Configuration validation failed:")
                for error in validation_result.errors:
                    logger.error(f"  - {error}")
                # Use fallback config on validation failure
                base_config = self._get_fallback_config()
                
            # Update internal state - cập nhật trạng thái nội bộ
            self._config = base_config
            self._last_reload = datetime.now()
            
            # Notify watchers - thông báo watchers
            self._notify_watchers(base_config)
            
            logger.info(f"✅ Configuration loaded successfully")
            return deepcopy(base_config)
    
    def _should_reload(self) -> bool:
        """
        Check if config should be reloaded.
        Kiểm tra có nên reload config không.
        """
        if not self.auto_reload:
            return False
            
        # Check file modification times
        for filepath, old_checksum in self._file_checksums.items():
            current_checksum = self._calculate_checksum(Path(filepath))
            if current_checksum != old_checksum:
                logger.debug(f"File changed: {filepath}")
                return True
                
        return False
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        Hợp nhất sâu hai dictionary.
        """
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
                
        return result
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """
        Get minimal fallback configuration.
        Lấy cấu hình dự phòng tối thiểu.
        """
        return {
            'system': {'enabled': True, 'debug_mode': False, 'log_level': 'INFO'},
            'metadata': {'version': '2.0.0', 'profile': 'fallback'},
            'orchestrator': {'max_workers': 2, 'scheduling_interval': 100},
            'monitoring': {'enabled': True, 'sampling_rate': 1000, 'buffer_size': 512},
            'strategies': {'default': 'conservative', 'available': ['conservative']},
            'resource_control': {'enabled': True},
            'coordination': {'enabled': True, 'max_concurrent_processes': 4},
            'profiling': {'enabled': False},
            'parallel_execution': {'enabled': True, 'max_parallel_tasks': 4}
        }
    
    def _notify_watchers(self, config: Dict[str, Any]):
        """
        Notify configuration watchers about changes.
        Thông báo watchers về thay đổi cấu hình.
        """
        for watcher in self._watchers:
            try:
                watcher(config)
            except Exception as e:
                logger.error(f"Error notifying watcher: {e}")
        
    def validate_config(self, 
                       config: Dict[str, Any], 
                       schema: Optional[ConfigSchema] = None) -> ConfigValidationResult:
        """
        Validate configuration against schema with detailed results.
        Xác thực cấu hình với schema và kết quả chi tiết.
        
        Args:
            config: Configuration to validate
            schema: Schema to validate against (defaults to MAIN_SCHEMA)
            
        Returns:
            ConfigValidationResult with validation details
        """
        schema = schema or self.MAIN_SCHEMA
        return schema.validate(config)
        
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation path.
        Lấy giá trị cấu hình theo đường dẫn dot-notation.
        
        Examples:
            config.get('system.enabled')  # True
            config.get('orchestrator.max_workers')  # 4
            config.get('unknown.key', 'default')  # 'default'
        
        Args:
            key_path: Dot-separated path to config value
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if not self._config:
            self._config = self.load_config()
            
        parts = key_path.split('.')
        current = self._config
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
                
        return current
    
    def set(self, key_path: str, value: Any, persist: bool = False):
        """
        Set configuration value at runtime.
        Đặt giá trị cấu hình tại runtime.
        
        Args:
            key_path: Dot-separated path to config value
            value: Value to set
            persist: Whether to save to file (not implemented yet)
        """
        if not self._config:
            self._config = self.load_config()
            
        self._set_nested_value(self._config, key_path, value)
        
        # Validate after change - xác thực sau khi thay đổi
        validation = self.validate_config(self._config)
        if not validation.is_valid:
            logger.warning(f"⚠️ Config invalid after set: {validation.errors}")
            
        # Notify watchers
        self._notify_watchers(self._config)
        
        if persist:
            logger.warning("Persist to file not implemented yet")
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get entire configuration dictionary.
        Lấy toàn bộ dictionary cấu hình.
        """
        if not self._config:
            self._config = self.load_config()
        return deepcopy(self._config)
    
    def reload(self):
        """
        Force reload configuration from disk.
        Buộc tải lại cấu hình từ đĩa.
        """
        logger.info("🔄 Force reloading configuration...")
        self._config = self.load_config(force_reload=True)
    
    def register_watcher(self, callback: callable):
        """
        Register callback for configuration changes.
        Đăng ký callback cho thay đổi cấu hình.
        
        Args:
            callback: Function to call on config change
        """
        if callback not in self._watchers:
            self._watchers.append(callback)
            logger.debug(f"Registered config watcher: {callback.__name__}")
    
    def unregister_watcher(self, callback: callable):
        """
        Unregister configuration watcher.
        Hủy đăng ký watcher cấu hình.
        """
        if callback in self._watchers:
            self._watchers.remove(callback)
            logger.debug(f"Unregistered config watcher: {callback.__name__}")
    
    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configurations using deep merge.
        Hợp nhất nhiều cấu hình dùng deep merge.
        
        Args:
            *configs: Configurations to merge
            
        Returns:
            Merged configuration
        """
        result = {}
        for config in configs:
            result = self._deep_merge(result, config)
        return result
        
    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration from file.
        Lấy cấu hình mặc định từ file.
        
        Returns:
            Default configuration dictionary
        """
        default_path = self.config_dir / self.DEFAULT_CONFIG_FILE
        if default_path.exists():
            return self.load_yaml(default_path)
        return self._get_fallback_config()
    
    def get_profile_config(self) -> Dict[str, Any]:
        """
        Get current profile configuration.
        Lấy cấu hình profile hiện tại.
        
        Returns:
            Profile configuration or empty dict
        """
        profile_path = self.config_dir / f"{self.profile}.yaml"
        if profile_path.exists():
            return self.load_yaml(profile_path)
        return {}
    
    def export_config(self, filepath: Path, format: str = 'yaml'):
        """
        Export current configuration to file.
        Xuất cấu hình hiện tại ra file.
        
        Args:
            filepath: Output file path
            format: Output format ('yaml' or 'json')
        """
        if not self._config:
            self._config = self.load_config()
            
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if format == 'yaml':
                    yaml.dump(self._config, f, default_flow_style=False, indent=2)
                elif format == 'json':
                    json.dump(self._config, f, indent=2)
                else:
                    raise ValueError(f"Unsupported format: {format}")
                    
            logger.info(f"✅ Exported config to {filepath}")
        except Exception as e:
            logger.error(f"❌ Failed to export config: {e}")
            raise


# Global singleton instance - instance singleton toàn cục
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """
    Get global ConfigLoader instance.
    Lấy instance ConfigLoader toàn cục.
    
    Returns:
        ConfigLoader singleton instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def load_config(name: str = "default", force_reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration (convenience function).
    Tải cấu hình (hàm tiện ích).
    
    Args:
        name: Configuration name
        force_reload: Force reload from disk
        
    Returns:
        Configuration dictionary
    """
    return get_config_loader().load_config(name, force_reload)


def get_config(key_path: str, default: Any = None) -> Any:
    """
    Get configuration value (convenience function).
    Lấy giá trị cấu hình (hàm tiện ích).
    
    Args:
        key_path: Dot-separated path to config value
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    return get_config_loader().get(key_path, default)


def set_config(key_path: str, value: Any, persist: bool = False):
    """
    Set configuration value (convenience function).
    Đặt giá trị cấu hình (hàm tiện ích).
    
    Args:
        key_path: Dot-separated path to config value
        value: Value to set
        persist: Whether to save to file
    """
    get_config_loader().set(key_path, value, persist)


def validate_config(config: Dict[str, Any]) -> ConfigValidationResult:
    """
    Validate configuration (convenience function).
    Xác thực cấu hình (hàm tiện ích).
    
    Args:
        config: Configuration to validate
        
    Returns:
        ConfigValidationResult with validation details
    """
    return get_config_loader().validate_config(config)


# Export classes and functions for public API
__all__ = [
    'ConfigLoader',
    'ConfigSchema', 
    'ConfigValidationResult',
    'get_config_loader',
    'load_config',
    'get_config',
    'set_config',
    'validate_config'
]
