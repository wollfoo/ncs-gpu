"""
GPU Optimization Validators Module.
Module validators cho tối ưu hóa GPU.

Provides comprehensive validation utilities for GPU operations.
Cung cấp các tiện ích validation toàn diện cho hoạt động GPU.
"""

import os
import re
from typing import Any, Callable, Dict, List, Optional, Union, Type
from functools import wraps
from pathlib import Path
import json
import yaml
from datetime import datetime
import inspect


# GPU-specific constants
VALID_GPU_VENDORS = ['nvidia', 'amd', 'intel']
VALID_MEMORY_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
VALID_POWER_STATES = ['P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']
VALID_COMPUTE_MODES = ['Default', 'Exclusive_Thread', 'Prohibited', 'Exclusive_Process']
MAX_GPU_TEMPERATURE = 100  # Celsius
MAX_GPU_POWER = 500  # Watts
MAX_GPU_MEMORY = 128 * 1024 * 1024 * 1024  # 128GB in bytes


class ValidationError(Exception):
    """
    Base validation error.
    Lỗi validation cơ bản.
    """
    pass


class Validator:
    """
    Base validator class with common validation methods.
    Lớp validator cơ bản với các phương thức validation chung.
    """
    
    @staticmethod
    def validate_type(value: Any, expected_type: Type, field_name: str = "value") -> Any:
        """
        Validate value type.
        Kiểm tra kiểu dữ liệu.
        
        Args:
            value: Value to validate
            expected_type: Expected type
            field_name: Field name for error message
            
        Returns:
            Validated value
            
        Raises:
            ValidationError: If type mismatch
        """
        if not isinstance(value, expected_type):
            raise ValidationError(
                f"{field_name} must be {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        return value
    
    @staticmethod
    def validate_range(value: Union[int, float], 
                      min_val: Optional[Union[int, float]] = None,
                      max_val: Optional[Union[int, float]] = None,
                      field_name: str = "value") -> Union[int, float]:
        """
        Validate numeric range.
        Kiểm tra khoảng giá trị số.
        
        Args:
            value: Numeric value
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive) 
            field_name: Field name for error message
            
        Returns:
            Validated value
            
        Raises:
            ValidationError: If out of range
        """
        if min_val is not None and value < min_val:
            raise ValidationError(
                f"{field_name} must be >= {min_val}, got {value}"
            )
        if max_val is not None and value > max_val:
            raise ValidationError(
                f"{field_name} must be <= {max_val}, got {value}"
            )
        return value
    
    @staticmethod
    def validate_enum(value: Any, valid_values: List[Any], 
                     field_name: str = "value") -> Any:
        """
        Validate value is in allowed list.
        Kiểm tra giá trị trong danh sách cho phép.
        
        Args:
            value: Value to check
            valid_values: List of valid values
            field_name: Field name for error message
            
        Returns:
            Validated value
            
        Raises:
            ValidationError: If not in valid values
        """
        if value not in valid_values:
            raise ValidationError(
                f"{field_name} must be one of {valid_values}, got {value}"
            )
        return value
    
    @staticmethod
    def validate_regex(value: str, pattern: str, 
                      field_name: str = "value") -> str:
        """
        Validate string matches regex pattern.
        Kiểm tra chuỗi khớp với regex pattern.
        
        Args:
            value: String to validate
            pattern: Regex pattern
            field_name: Field name for error message
            
        Returns:
            Validated value
            
        Raises:
            ValidationError: If pattern doesn't match
        """
        if not re.match(pattern, value):
            raise ValidationError(
                f"{field_name} does not match pattern {pattern}: {value}"
            )
        return value
    
    @staticmethod
    def validate_path(path: Union[str, Path], 
                     must_exist: bool = False,
                     must_be_file: Optional[bool] = None,
                     must_be_dir: Optional[bool] = None,
                     path_type: Optional[str] = None) -> Path:
        """
        Validate file system path.
        Kiểm tra đường dẫn file system.
        
        Args:
            path: Path to validate
            must_exist: Whether path must exist
            must_be_file: Whether path must be a file (deprecated, use path_type)
            must_be_dir: Whether path must be a directory (deprecated, use path_type)
            path_type: Type of path ('file' or 'dir')
            
        Returns:
            Validated Path object
            
        Raises:
            ValidationError: If validation fails
        """
        path_obj = Path(path)
        
        if must_exist and not path_obj.exists():
            raise ValidationError(f"Path does not exist: {path}")
        
        # Support both old and new API
        if path_type == 'file':
            must_be_file = True
        elif path_type == 'dir':
            must_be_dir = True
            
        if must_be_file is not None:
            if must_be_file and path_obj.exists() and not path_obj.is_file():
                raise ValidationError(f"Path is not a file: {path}")
            elif not must_be_file and path_obj.is_file():
                raise ValidationError(f"Path should not be a file: {path}")
                
        if must_be_dir is not None:
            if must_be_dir and not path_obj.is_dir():
                raise ValidationError(f"Path is not a directory: {path}")
            elif not must_be_dir and path_obj.is_dir():
                raise ValidationError(f"Path should not be a directory: {path}")
                
        return path_obj


class GPUValidator(Validator):
    """
    GPU-specific validators.
    Validators dành riêng cho GPU.
    """
    
    @classmethod
    def validate_gpu_id(cls, gpu_id: Union[int, str]) -> int:
        """
        Validate GPU ID.
        Kiểm tra GPU ID.
        
        Args:
            gpu_id: GPU identifier
            
        Returns:
            Validated GPU ID as integer
            
        Raises:
            ValidationError: If invalid GPU ID
        """
        try:
            gpu_id = int(gpu_id)
            return cls.validate_range(gpu_id, 0, 15, "GPU ID")
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid GPU ID: {gpu_id}")
    
    @classmethod
    def validate_gpu_memory(cls, memory: Union[int, str]) -> int:
        """
        Validate GPU memory value.
        Kiểm tra giá trị bộ nhớ GPU.
        
        Args:
            memory: Memory value (bytes or string with unit)
            
        Returns:
            Memory in bytes
            
        Raises:
            ValidationError: If invalid memory value
        """
        # If memory is int or float, treat it as MB for backward compatibility
        if isinstance(memory, (int, float)):
            memory_bytes = int(memory * 1024 * 1024)  # MB → bytes
            return cls.validate_range(memory_bytes, 0, MAX_GPU_MEMORY, "GPU memory (MB)")
        
        if isinstance(memory, str):
            # Parse memory string like "8GB", "4096MB"
            match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B)$', memory.upper())
            if not match:
                raise ValidationError(f"Invalid memory format: {memory}")
                
            value, unit = match.groups()
            value = float(value)
            
            # Convert to bytes
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 
                          'GB': 1024**3, 'TB': 1024**4}
            memory = int(value * multipliers[unit])
            
        return cls.validate_range(memory, 0, MAX_GPU_MEMORY, "GPU memory")
    
    @classmethod
    def validate_gpu_temperature(cls, temp: Union[int, float]) -> float:
        """
        Validate GPU temperature.
        Kiểm tra nhiệt độ GPU.
        
        Args:
            temp: Temperature in Celsius
            
        Returns:
            Validated temperature
            
        Raises:
            ValidationError: If invalid temperature
        """
        temp = float(temp)
        return cls.validate_range(temp, 0, MAX_GPU_TEMPERATURE, "GPU temperature")
    
    @classmethod
    def validate_gpu_power(cls, power: Union[int, float]) -> float:
        """
        Validate GPU power consumption.
        Kiểm tra mức tiêu thụ điện GPU.
        
        Args:
            power: Power in watts
            
        Returns:
            Validated power value
            
        Raises:
            ValidationError: If invalid power value
        """
        power = float(power)
        return cls.validate_range(power, 0, MAX_GPU_POWER, "GPU power")
    
    @classmethod
    def validate_gpu_utilization(cls, utilization: Union[int, float]) -> float:
        """
        Validate GPU utilization percentage.
        Kiểm tra phần trăm sử dụng GPU.
        
        Args:
            utilization: Utilization percentage (0-100)
            
        Returns:
            Validated utilization
            
        Raises:
            ValidationError: If invalid utilization
        """
        utilization = float(utilization)
        return cls.validate_range(utilization, 0, 100, "GPU utilization")
    
    @classmethod
    def validate_clock_speed(cls, clock: Union[int, str]) -> int:
        """
        Validate GPU clock speed.
        Kiểm tra tốc độ xung nhịp GPU.
        
        Args:
            clock: Clock speed in MHz or string with unit
            
        Returns:
            Clock speed in MHz
            
        Raises:
            ValidationError: If invalid clock speed
        """
        if isinstance(clock, str):
            # Parse clock string like "1500MHz", "1.5GHz"
            match = re.match(r'^(\d+(?:\.\d+)?)\s*([MG]Hz)$', clock.upper())
            if not match:
                raise ValidationError(f"Invalid clock format: {clock}")
                
            value, unit = match.groups()
            value = float(value)
            
            # Convert to MHz
            if unit == 'GHZ':
                clock = int(value * 1000)
            else:
                clock = int(value)
                
        return cls.validate_range(clock, 0, 5000, "Clock speed")
    
    @classmethod
    def validate_power_state(cls, state: str) -> str:
        """
        Validate GPU power state.
        Kiểm tra trạng thái năng lượng GPU.
        
        Args:
            state: Power state (P0-P8)
            
        Returns:
            Validated power state
            
        Raises:
            ValidationError: If invalid power state
        """
        state = state.upper()
        return cls.validate_enum(state, VALID_POWER_STATES, "Power state")
    
    @classmethod
    def validate_compute_mode(cls, mode: str) -> str:
        """
        Validate GPU compute mode.
        Kiểm tra chế độ tính toán GPU.
        
        Args:
            mode: Compute mode
            
        Returns:
            Validated compute mode
            
        Raises:
            ValidationError: If invalid compute mode
        """
        return cls.validate_enum(mode, VALID_COMPUTE_MODES, "Compute mode")


def validate_decorator(**param_validators):
    """
    Decorator to validate function parameters.
    Decorator để validate tham số hàm.
    
    Args:
        **param_validators: Dict of param_name: (type, constraint_func) pairs
        
    Example:
        @validate_decorator(
            gpu_id=(int, lambda x: 0 <= x < 8),
            memory=(int, lambda x: x > 0)
        )
        def process_gpu(gpu_id: int, memory: int):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate each specified parameter
            for param_name, (expected_type, constraint) in param_validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    
                    # Type check
                    if not isinstance(value, expected_type):
                        raise ValidationError(
                            f"Parameter '{param_name}' must be {expected_type.__name__}, "
                            f"got {type(value).__name__}"
                        )
                    
                    # Constraint check
                    if constraint and not constraint(value):
                        raise ValidationError(
                            f"Parameter '{param_name}' with value {value} "
                            f"failed constraint validation"
                        )
                    
            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper
    return decorator


def validate_config(config: Dict[str, Any], 
                   schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate configuration dictionary.
    Kiểm tra dictionary cấu hình.
    
    Args:
        config: Configuration dictionary
        schema: Optional schema for validation
        
    Returns:
        Validated config
        
    Raises:
        ValidationError: If validation fails
    """
    if schema:
        # Support tuple-based schema: key -> (type, constraint_func)
        tuple_style = all(isinstance(v, tuple) and len(v) == 2 for v in schema.values())
        if tuple_style:
            for key, (expected_type, constraint) in schema.items():
                if key not in config:
                    raise ValidationError(f"Missing required config key: {key}")
                value = config[key]
                if not isinstance(value, expected_type):
                    raise ValidationError(f"Config {key} must be {expected_type.__name__}")
                if constraint and not constraint(value):
                    raise ValidationError(f"Config {key} failed constraint validation: {value}")
            return config
        
        # Dict-style schema existing behaviour
        for key, rules in schema.items():
            if 'required' in rules and rules['required']:
                if key not in config:
                    raise ValidationError(f"Missing required config key: {key}")
                    
            if key in config:
                value = config[key]
                
                # Type validation
                if 'type' in rules:
                    expected_type = rules['type']
                    if not isinstance(value, expected_type):
                        raise ValidationError(
                            f"Config {key} must be {expected_type.__name__}"
                        )
                        
                # Range validation
                if 'min' in rules:
                    if value < rules['min']:
                        raise ValidationError(
                            f"Config {key} must be >= {rules['min']}"
                        )
                if 'max' in rules:
                    if value > rules['max']:
                        raise ValidationError(
                            f"Config {key} must be <= {rules['max']}"
                        )
                        
                # Enum validation
                if 'enum' in rules:
                    if value not in rules['enum']:
                        raise ValidationError(
                            f"Config {key} must be one of {rules['enum']}"
                        )
                        
    return config


def validate_batch_operation(items: List[Any], 
                            validation_func: Callable,
                            continue_on_error: bool = False) -> List[Dict[str, Any]]:
    """
    Validate batch of items.
    Kiểm tra batch các items.
    
    Args:
        items: List of items to validate
        validation_func: Function to validate each item
        continue_on_error: Whether to continue on validation error
        
    Returns:
        List of validation results with 'success', 'value', and 'error' keys
        
    Raises:
        ValidationError: If validation fails and continue_on_error is False
    """
    results = []
    
    for i, item in enumerate(items):
        try:
            validated = validation_func(item)
            results.append({
                'success': True,
                'value': validated,
                'error': None,
                'index': i
            })
        except ValidationError as e:
            if continue_on_error:
                results.append({
                    'success': False,
                    'value': None,
                    'error': str(e),
                    'index': i
                })
            else:
                raise ValidationError(f"Batch validation failed at item {i}: {str(e)}")
                
    # Log errors if any
    errors = [r for r in results if not r['success']]
    if errors and continue_on_error:
        from .logger import get_logger
        logger = get_logger('validators')
        for error_result in errors:
            logger.warning(f"Batch validation error at index {error_result['index']}: {error_result['error']}")
            
    return results
