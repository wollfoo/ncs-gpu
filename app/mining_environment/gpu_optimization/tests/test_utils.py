"""
Test suite for GPU Optimization Utils module.
Test suite cho module utils tối ưu hóa GPU.

Tests logger, validators, and exceptions functionality.
Kiểm thử chức năng logger, validators, và exceptions.
"""

import os
import sys
import json
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gpu_optimization.utils import (
    # Logger
    GPULogger,
    get_logger,
    log_execution_time,
    log_errors,
    
    # Validators
    ValidationError,
    Validator,
    GPUValidator,
    validate_decorator,
    validate_config,
    validate_batch_operation,
    
    # Exceptions
    GPUOptimizationError,
    GPUNotFoundError,
    GPUMemoryError,
    GPUTemperatureError,
    ConfigurationError,
    InvalidConfigError,
    OrchestrationError,
    handle_exception
)


class TestLogger(unittest.TestCase):
    """Test cases for logger module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton instance
        GPULogger._instance = None
        
        # Create temp directory for logs
        self.temp_dir = tempfile.mkdtemp()
        os.environ['GPU_OPT_LOG_DIR'] = self.temp_dir
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Reset singleton
        GPULogger._instance = None
        
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
        # Clear environment
        if 'GPU_OPT_LOG_DIR' in os.environ:
            del os.environ['GPU_OPT_LOG_DIR']
            
    def test_singleton_pattern(self):
        """Test logger singleton pattern."""
        logger1 = GPULogger()
        logger2 = GPULogger()
        self.assertIs(logger1, logger2)
        
    def test_get_logger(self):
        """Test getting module logger."""
        logger = get_logger('test_module')
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, 'test_module')
        
    def test_log_levels(self):
        """Test different log levels."""
        logger = get_logger('test')
        
        # Test all log levels
        with patch.object(logger, 'debug') as mock_debug:
            logger.debug("Debug message")
            mock_debug.assert_called_once()
            
        with patch.object(logger, 'info') as mock_info:
            logger.info("Info message")
            mock_info.assert_called_once()
            
        with patch.object(logger, 'warning') as mock_warning:
            logger.warning("Warning message")
            mock_warning.assert_called_once()
            
        with patch.object(logger, 'error') as mock_error:
            logger.error("Error message")
            mock_error.assert_called_once()
            
        with patch.object(logger, 'critical') as mock_critical:
            logger.critical("Critical message")
            mock_critical.assert_called_once()
            
    def test_context_manager(self):
        """Test logger context manager."""
        gpu_logger = GPULogger()
        logger = get_logger('test')
        
        with gpu_logger.context(request_id='test-123'):
            # Context should be added to log
            with patch.object(logger, 'info') as mock_info:
                logger.info("Test message")
                # Check if context is in extra
                call_args = mock_info.call_args
                self.assertIn('extra', call_args[1])
                self.assertEqual(call_args[1]['extra']['request_id'], 'test-123')
                
    def test_log_execution_time_decorator(self):
        """Test execution time logging decorator."""
        @log_execution_time
        def slow_function():
            time.sleep(0.1)
            return "done"
            
        with patch('logging.Logger.info') as mock_info:
            result = slow_function()
            self.assertEqual(result, "done")
            # Check if execution time was logged
            mock_info.assert_called()
            call_msg = str(mock_info.call_args)
            self.assertIn('slow_function', call_msg)
            
    def test_log_exceptions_decorator(self):
        """Test exception logging decorator."""
        @log_errors
        def failing_function():
            raise ValueError("Test error")
            
        with patch('logging.Logger.exception') as mock_exception:
            with self.assertRaises(ValueError):
                failing_function()
            # Check if exception was logged
            mock_exception.assert_called()
            
    def test_file_logging(self):
        """Test file logging functionality."""
        gpu_logger = GPULogger()
        logger = get_logger('test')
        
        # Log a message
        logger.info("Test file logging")
        
        # Check if log file exists
        log_file = Path(self.temp_dir) / 'gpu_optimization.log'
        self.assertTrue(log_file.exists())
        
        # Check log content
        with open(log_file, 'r') as f:
            content = f.read()
            self.assertIn("Test file logging", content)
            
    def test_structured_logging(self):
        """Test structured JSON logging."""
        # Enable structured logging
        os.environ['GPU_OPT_STRUCTURED_LOGGING'] = 'true'
        
        # Reset singleton to pick up new config
        GPULogger._instance = None
        gpu_logger = GPULogger()
        logger = get_logger('test')
        
        # Create a temp file for structured logs
        structured_log = Path(self.temp_dir) / 'structured.log'
        
        # Add handler for structured logging
        import logging
        handler = logging.FileHandler(structured_log)
        handler.setFormatter(gpu_logger.structured_formatter)
        logger.addHandler(handler)
        
        # Log a message with extra data
        logger.info("Test structured", extra={'gpu_id': 0, 'memory': 1024})
        
        # Read and parse JSON log
        with open(structured_log, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            
            self.assertEqual(log_data['message'], "Test structured")
            self.assertEqual(log_data['gpu_id'], 0)
            self.assertEqual(log_data['memory'], 1024)
            self.assertIn('timestamp', log_data)


class TestValidators(unittest.TestCase):
    """Test cases for validators module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = Validator()
        self.gpu_validator = GPUValidator()
        
    def test_validate_type(self):
        """Test type validation."""
        # Valid cases
        self.validator.validate_type(42, int, "test_value")
        self.validator.validate_type("hello", str, "test_value")
        self.validator.validate_type([1, 2], list, "test_value")
        
        # Invalid case
        with self.assertRaises(ValidationError) as cm:
            self.validator.validate_type("42", int, "test_value")
        self.assertIn("test_value", str(cm.exception))
        self.assertIn("int", str(cm.exception))
        
    def test_validate_range(self):
        """Test range validation."""
        # Valid cases
        self.validator.validate_range(5, 0, 10, "test_value")
        self.validator.validate_range(0, 0, 10, "test_value")
        self.validator.validate_range(10, 0, 10, "test_value")
        
        # Invalid cases
        with self.assertRaises(ValidationError):
            self.validator.validate_range(-1, 0, 10, "test_value")
            
        with self.assertRaises(ValidationError):
            self.validator.validate_range(11, 0, 10, "test_value")
            
    def test_validate_enum(self):
        """Test enum validation."""
        # Valid case
        self.validator.validate_enum("apple", ["apple", "banana", "orange"], "fruit")
        
        # Invalid case
        with self.assertRaises(ValidationError) as cm:
            self.validator.validate_enum("grape", ["apple", "banana"], "fruit")
        self.assertIn("fruit", str(cm.exception))
        self.assertIn("grape", str(cm.exception))
        
    def test_validate_regex(self):
        """Test regex validation."""
        # Valid cases
        self.validator.validate_regex("test@example.com", r'^[\w\.-]+@[\w\.-]+\.\w+$', "email")
        self.validator.validate_regex("123-45-6789", r'^\d{3}-\d{2}-\d{4}$', "ssn")
        
        # Invalid case
        with self.assertRaises(ValidationError):
            self.validator.validate_regex("invalid-email", r'^[\w\.-]+@[\w\.-]+\.\w+$', "email")
            
    def test_validate_path(self):
        """Test path validation."""
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # Valid case
            self.validator.validate_path(tmp_path, must_exist=True, path_type='file')
            
            # Invalid case - file doesn't exist
            with self.assertRaises(ValidationError):
                self.validator.validate_path("/nonexistent/path", must_exist=True)
                
        finally:
            os.unlink(tmp_path)
            
    def test_gpu_validate_id(self):
        """Test GPU ID validation."""
        # Valid cases
        self.gpu_validator.validate_gpu_id(0)
        self.gpu_validator.validate_gpu_id(7)
        
        # Invalid cases
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_id(-1)
            
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_id(100)
            
    def test_gpu_validate_memory(self):
        """Test GPU memory validation."""
        # Valid cases
        self.gpu_validator.validate_gpu_memory(1024)
        self.gpu_validator.validate_gpu_memory(8192)
        
        # Invalid cases
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_memory(-100)
            
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_memory(1000000)  # 1TB is too much
            
    def test_gpu_validate_temperature(self):
        """Test GPU temperature validation."""
        # Valid cases
        self.gpu_validator.validate_gpu_temperature(50.0)
        self.gpu_validator.validate_gpu_temperature(85.0)
        
        # Invalid cases
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_temperature(-10.0)
            
        with self.assertRaises(ValidationError):
            self.gpu_validator.validate_gpu_temperature(150.0)
            
    def test_validate_decorator(self):
        """Test validation decorator."""
        @validate_decorator(
            gpu_id=(int, lambda x: 0 <= x < 8),
            memory=(int, lambda x: x > 0)
        )
        def gpu_function(gpu_id, memory):
            return f"GPU {gpu_id} with {memory}MB"
            
        # Valid call
        result = gpu_function(0, 1024)
        self.assertEqual(result, "GPU 0 with 1024MB")
        
        # Invalid calls
        with self.assertRaises(ValidationError):
            gpu_function(-1, 1024)  # Invalid GPU ID
            
        with self.assertRaises(ValidationError):
            gpu_function(0, -100)  # Invalid memory
            
    def test_validate_config(self):
        """Test config validation."""
        schema = {
            'gpu_id': (int, lambda x: 0 <= x < 8),
            'memory': (int, lambda x: x > 0),
            'name': (str, lambda x: len(x) > 0)
        }
        
        # Valid config
        config = {'gpu_id': 0, 'memory': 1024, 'name': 'test'}
        validated = validate_config(config, schema)
        self.assertEqual(validated, config)
        
        # Invalid config - wrong type
        with self.assertRaises(ValidationError):
            validate_config({'gpu_id': '0', 'memory': 1024, 'name': 'test'}, schema)
            
        # Invalid config - constraint violation
        with self.assertRaises(ValidationError):
            validate_config({'gpu_id': 10, 'memory': 1024, 'name': 'test'}, schema)
            
    def test_validate_batch_operation(self):
        """Test batch validation."""
        def validate_item(item):
            if not isinstance(item, dict):
                raise ValidationError("Item must be dict")
            if 'id' not in item:
                raise ValidationError("Item must have id")
            return item
            
        # All valid
        items = [{'id': 1}, {'id': 2}, {'id': 3}]
        results = validate_batch_operation(items, validate_item)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r['success'] for r in results))
        
        # Some invalid, continue on error
        items = [{'id': 1}, 'invalid', {'id': 3}]
        results = validate_batch_operation(items, validate_item, continue_on_error=True)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['success'])
        self.assertFalse(results[1]['success'])
        self.assertTrue(results[2]['success'])
        
        # Some invalid, stop on error
        with self.assertRaises(ValidationError):
            validate_batch_operation(items, validate_item, continue_on_error=False)


class TestExceptions(unittest.TestCase):
    """Test cases for exceptions module."""
    
    def test_base_exception(self):
        """Test base GPU optimization error."""
        exc = GPUOptimizationError(
            "Test error",
            error_code="TEST_001",
            details={'key': 'value'},
            suggestions=['Fix this', 'Try that']
        )
        
        self.assertEqual(exc.message, "Test error")
        self.assertEqual(exc.error_code, "TEST_001")
        self.assertEqual(exc.details, {'key': 'value'})
        self.assertEqual(exc.suggestions, ['Fix this', 'Try that'])
        self.assertIsNotNone(exc.timestamp)
        
        # Test string representation
        str_repr = str(exc)
        self.assertIn("[TEST_001]", str_repr)
        self.assertIn("Test error", str_repr)
        self.assertIn("Fix this", str_repr)
        
        # Test dict conversion
        exc_dict = exc.to_dict()
        self.assertEqual(exc_dict['error_type'], 'GPUOptimizationError')
        self.assertEqual(exc_dict['message'], "Test error")
        self.assertIn('traceback', exc_dict)
        
    def test_gpu_not_found_error(self):
        """Test GPU not found error."""
        exc = GPUNotFoundError(gpu_id=2)
        
        self.assertIn("GPU 2 not found", exc.message)
        self.assertEqual(exc.details['gpu_id'], 2)
        self.assertTrue(len(exc.suggestions) > 0)
        self.assertIn("nvidia-smi", str(exc.suggestions))
        
    def test_gpu_memory_error(self):
        """Test GPU memory error."""
        exc = GPUMemoryError(required=8192, available=4096, gpu_id=0)
        
        self.assertIn("8192", exc.message)
        self.assertIn("4096", exc.message)
        self.assertEqual(exc.details['required_mb'], 8192)
        self.assertEqual(exc.details['available_mb'], 4096)
        self.assertEqual(exc.details['gpu_id'], 0)
        self.assertIn("batch size", str(exc.suggestions))
        
    def test_gpu_temperature_error(self):
        """Test GPU temperature error."""
        exc = GPUTemperatureError(temperature=95.0, threshold=85.0, gpu_id=1)
        
        self.assertIn("95", exc.message)
        self.assertIn("85", exc.message)
        self.assertEqual(exc.details['temperature'], 95.0)
        self.assertEqual(exc.details['threshold'], 85.0)
        self.assertIn("cooling", str(exc.suggestions))
        
    def test_configuration_error(self):
        """Test configuration error."""
        exc = InvalidConfigError(
            config_key='batch_size',
            value='invalid',
            expected='positive integer'
        )
        
        self.assertIn("batch_size", exc.message)
        self.assertIn("invalid", exc.message)
        self.assertIn("positive integer", exc.message)
        self.assertEqual(exc.details['value'], 'invalid')
        self.assertEqual(exc.details['expected'], 'positive integer')
        
    def test_orchestration_error(self):
        """Test orchestration error."""
        exc = OrchestrationError("Worker pool failed")
        
        self.assertEqual(exc.message, "Worker pool failed")
        self.assertEqual(exc.error_code, "ORCH_ERROR")
        
    def test_handle_exception(self):
        """Test exception handler."""
        # Test with GPU optimization error
        gpu_exc = GPUNotFoundError(gpu_id=0)
        
        with patch('gpu_optimization.utils.exceptions.traceback.format_exc', return_value='mock traceback'):
            # Handle without reraising
            result = handle_exception(gpu_exc, reraise=False)
            
            self.assertIsInstance(result, dict)
            self.assertEqual(result['error_type'], 'GPUNotFoundError')
            self.assertIn('GPU 0', result['message'])
            
        # Test with regular exception
        regular_exc = ValueError("Regular error")
        
        with patch('gpu_optimization.utils.exceptions.traceback.format_exc', return_value='mock traceback'):
            result = handle_exception(regular_exc, reraise=False)
            
            self.assertEqual(result['error_type'], 'ValueError')
            self.assertEqual(result['message'], "Regular error")
            
        # Test with logger
        mock_logger = Mock()
        handle_exception(gpu_exc, logger=mock_logger, reraise=False)
        mock_logger.error.assert_called_once()
        
        # Test reraise
        with self.assertRaises(GPUNotFoundError):
            handle_exception(gpu_exc, reraise=True)


class TestIntegration(unittest.TestCase):
    """Integration tests for utils module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton
        GPULogger._instance = None
        
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()
        os.environ['GPU_OPT_LOG_DIR'] = self.temp_dir
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Reset singleton
        GPULogger._instance = None
        
        # Clean up
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
        if 'GPU_OPT_LOG_DIR' in os.environ:
            del os.environ['GPU_OPT_LOG_DIR']
            
    def test_logger_with_exceptions(self):
        """Test logger integration with exceptions."""
        logger = get_logger('test')
        
        @log_errors
        def failing_function():
            raise GPUMemoryError(required=8192, available=4096)
            
        with patch.object(logger, 'exception') as mock_exception:
            with self.assertRaises(GPUMemoryError):
                failing_function()
                
            mock_exception.assert_called()
            
    def test_validator_with_decorator_and_exception(self):
        """Test validator decorator with custom exceptions."""
        @validate_decorator(
            gpu_id=(int, lambda x: 0 <= x < 8)
        )
        def allocate_gpu(gpu_id):
            if gpu_id == 7:
                raise GPUNotFoundError(gpu_id=gpu_id)
            return f"Allocated GPU {gpu_id}"
            
        # Valid call
        result = allocate_gpu(0)
        self.assertEqual(result, "Allocated GPU 0")
        
        # Invalid validation
        with self.assertRaises(ValidationError):
            allocate_gpu(10)
            
        # Function raises exception
        with self.assertRaises(GPUNotFoundError):
            allocate_gpu(7)
            
    def test_complete_error_flow(self):
        """Test complete error handling flow."""
        logger = get_logger('test')
        validator = GPUValidator()
        
        def process_gpu_request(gpu_id, memory):
            try:
                # Validate inputs
                validator.validate_gpu_id(gpu_id)
                validator.validate_gpu_memory(memory)
                
                # Simulate GPU operation
                if memory > 8192:
                    raise GPUMemoryError(required=memory, available=8192, gpu_id=gpu_id)
                    
                return f"Success: GPU {gpu_id} allocated {memory}MB"
                
            except ValidationError as e:
                # Log validation error
                error_dict = handle_exception(e, logger=logger, reraise=False)
                return f"Validation failed: {error_dict['message']}"
                
            except GPUMemoryError as e:
                # Log GPU error
                error_dict = handle_exception(e, logger=logger, reraise=False)
                return f"GPU error: {error_dict['message']}"
                
        # Test successful request
        result = process_gpu_request(0, 4096)
        self.assertIn("Success", result)
        
        # Test validation failure
        result = process_gpu_request(-1, 4096)
        self.assertIn("Validation failed", result)
        
        # Test GPU error
        with patch.object(logger, 'error'):
            result = process_gpu_request(0, 16384)
            self.assertIn("GPU error", result)
            self.assertIn("16384", result)


if __name__ == '__main__':
    unittest.main()
