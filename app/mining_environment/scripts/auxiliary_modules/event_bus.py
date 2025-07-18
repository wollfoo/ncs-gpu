from __future__ import annotations

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, Any, List, DefaultDict, Optional

import jsonschema
from jsonschema import ValidationError


class EventBusBackend(ABC):
    """Interface cho các backend driver của EventBus.
    
    Mỗi backend (memory, redis, kafka) phải implement các method này.
    """
    
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới topic."""
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho topic."""
        pass
    
    @abstractmethod
    def start_listening(self) -> None:
        """Khởi động background listener (nếu cần)."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Dừng và cleanup resources."""
        pass


class MemoryEventBusBackend(EventBusBackend):
    """Backend driver cho EventBus sử dụng bộ nhớ (in-process)."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới tất cả subscribers của topic."""
        callbacks: List[Callable[[Dict[str, Any]], None]]
        with self._lock:
            callbacks = list(self._subscribers.get(topic, []))
        
        # Gọi callback ngoài lock để tránh deadlock
        for cb in callbacks:
            try:
                cb(payload)
            except Exception as exc:
                self._logger.error(
                    "Lỗi khi gọi callback cho topic '%s': %s", topic, exc, exc_info=True
                )
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho topic."""
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
    
    def start_listening(self) -> None:
        """Không cần implement cho memory backend."""
        pass
    
    def stop(self) -> None:
        """Huỷ tất cả subscriptions."""
        with self._lock:
            self._subscribers.clear()


class RedisEventBusBackend(EventBusBackend):
    """Backend driver cho EventBus sử dụng Redis Pub/Sub."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        # TODO: Implement Redis connection và pub/sub logic
        raise NotImplementedError("Redis backend sẽ được implement trong Phase 2-4")
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError("Redis backend sẽ được implement trong Phase 2-4")
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        raise NotImplementedError("Redis backend sẽ được implement trong Phase 2-4")
    
    def start_listening(self) -> None:
        raise NotImplementedError("Redis backend sẽ được implement trong Phase 2-4")
    
    def stop(self) -> None:
        raise NotImplementedError("Redis backend sẽ được implement trong Phase 2-4")


class KafkaEventBusBackend(EventBusBackend):
    """Backend driver cho EventBus sử dụng Kafka."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        # TODO: Implement Kafka producer/consumer logic
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def start_listening(self) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")
    
    def stop(self) -> None:
        raise NotImplementedError("Kafka backend sẽ được implement trong Phase 5-6")


class EventBusSchemaValidator:
    """Validator cho JSON Schema của EventBus messages."""
    
    def __init__(self, schema_dir: str | Path | None = None) -> None:
        if schema_dir is None:
            # Mặc định schema nằm cùng thư mục với event_bus.py
            schema_dir = Path(__file__).parent / "schemas"
        
        self._schema_dir = Path(schema_dir)
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)
        
        # Load tất cả schemas lúc khởi tạo
        self._load_schemas()
    
    def _load_schemas(self) -> None:
        """Load tất cả schema files từ thư mục schemas."""
        if not self._schema_dir.exists():
            self._logger.warning(f"Schema directory không tồn tại: {self._schema_dir}")
            return
        
        for schema_file in self._schema_dir.glob("*.json"):
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                
                # Tên schema = tên file không có extension
                schema_name = schema_file.stem
                self._schemas[schema_name] = schema_data
                self._logger.debug(f"Loaded schema: {schema_name}")
                
            except Exception as exc:
                self._logger.error(f"Lỗi khi load schema {schema_file}: {exc}")
    
    def validate(self, topic: str, payload: Dict[str, Any]) -> None:
        """Validate payload theo schema của topic.
        
        Args:
            topic: Tên topic (sẽ map với schema file)
            payload: Dữ liệu cần validate
            
        Raises:
            ValidationError: Khi payload không hợp lệ
        """
        # Tìm schema tương ứng với topic
        schema = self._schemas.get(topic)
        if not schema:
            # Nếu không có schema cụ thể, sử dụng schema mặc định
            schema = self._schemas.get("default")
        
        if not schema:
            self._logger.warning(f"Không tìm thấy schema cho topic '{topic}'")
            return
        
        try:
            jsonschema.validate(payload, schema)
        except ValidationError as exc:
            self._logger.error(f"Schema validation failed cho topic '{topic}': {exc}")
            raise


class EventBus:
    """EventBus chính với hỗ trợ đa backend và schema validation.
    
    Sử dụng Adapter Pattern để hỗ trợ hot-swap backend driver.
    """
    
    def __init__(self, backend_type: Optional[str] = None, 
                 schema_dir: Optional[str] = None,
                 logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        
        # Xác định backend type từ environment variable hoặc parameter
        if backend_type is None:
            backend_type = os.getenv("EVENT_BUS_BACKEND", "memory")
        
        # Khởi tạo backend driver
        self._backend = self._create_backend(backend_type)
        
        # Khởi tạo schema validator
        self._validator = EventBusSchemaValidator(schema_dir)
        
        self._logger.info(f"EventBus initialized with backend: {backend_type}")
    
    def _create_backend(self, backend_type: str) -> EventBusBackend:
        """Factory method để tạo backend driver."""
        backend_map = {
            "memory": MemoryEventBusBackend,
            "redis": RedisEventBusBackend,
            "kafka": KafkaEventBusBackend,
        }
        
        backend_class = backend_map.get(backend_type.lower())
        if not backend_class:
            raise ValueError(f"Không hỗ trợ backend type: {backend_type}")
        
        return backend_class(self._logger)
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới topic với schema validation.
        
        Args:
            topic: Tên topic
            payload: Dữ liệu sự kiện (phải là dict)
            
        Raises:
            TypeError: Khi payload không phải dict
            ValidationError: Khi payload không hợp lệ với schema
        """
        if not isinstance(payload, dict):
            raise TypeError("EventBus payload phải là dict")
        
        # Validate schema trước khi publish
        try:
            self._validator.validate(topic, payload)
        except ValidationError:
            # Re-raise validation error để caller xử lý
            raise
        
        # Gửi tới backend
        self._backend.publish(topic, payload)
        
        self._logger.debug(f"Published event to topic '{topic}': {payload}")
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho topic.
        
        Args:
            topic: Tên topic
            callback: Hàm callback nhận Dict[str, Any]
        """
        self._backend.subscribe(topic, callback)
        self._logger.debug(f"Subscribed to topic '{topic}'")
    
    def start_listening(self) -> None:
        """Khởi động background listener (cho Redis/Kafka backends)."""
        self._backend.start_listening()
    
    def stop(self) -> None:
        """Dừng EventBus và cleanup resources."""
        self._backend.stop()
        self._logger.info("EventBus stopped")


# Singleton instance cho convenience
_event_bus_instance: Optional[EventBus] = None
_instance_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Lấy singleton instance của EventBus."""
    global _event_bus_instance
    
    if _event_bus_instance is None:
        with _instance_lock:
            if _event_bus_instance is None:
                _event_bus_instance = EventBus()
    
    return _event_bus_instance


def publish(topic: str, payload: Dict[str, Any]) -> None:
    """Convenience function để publish sự kiện."""
    get_event_bus().publish(topic, payload)


def subscribe(topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
    """Convenience function để subscribe topic."""
    get_event_bus().subscribe(topic, callback)


def start_listening() -> None:
    """Convenience function để start listening."""
    get_event_bus().start_listening()


def stop() -> None:
    """Convenience function để stop EventBus."""
    get_event_bus().stop()