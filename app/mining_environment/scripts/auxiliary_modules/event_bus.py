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
        self._redis_client = None
        self._pubsub = None
        self._listener_thread = None
        self._stop_listening = False
        self._lock = threading.RLock()
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        
        # Redis connection configuration
        self._redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'db': int(os.getenv('REDIS_DB', '0')),
            'password': os.getenv('REDIS_PASSWORD', None),
            'decode_responses': True,
            'socket_timeout': 5.0,
            'socket_connect_timeout': 5.0,
            'retry_on_timeout': True,
            'health_check_interval': 30
        }
        
        # Retry configuration
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 0.1,
            'max_delay': 1.0,
            'backoff_factor': 2.0
        }
        
        # Initialize Redis connection
        self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """Khởi tạo kết nối Redis với retry logic."""
        try:
            import redis
            self._redis_client = redis.Redis(**self._redis_config)
            
            # Test connection
            self._redis_client.ping()
            self._logger.info("Redis connection established successfully")
            
            # Initialize pubsub
            self._pubsub = self._redis_client.pubsub()
            
        except ImportError:
            raise ImportError("Redis package not installed. Run: pip install redis>=4.5.0")
        except Exception as e:
            self._logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    def _retry_operation(self, operation, *args, **kwargs):
        """Retry logic cho Redis operations với exponential backoff."""
        retry_count = 0
        delay = self._retry_config['base_delay']
        
        while retry_count < self._retry_config['max_retries']:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                if retry_count >= self._retry_config['max_retries']:
                    self._logger.error(f"Redis operation failed after {retry_count} retries: {e}")
                    raise
                
                self._logger.warning(f"Redis operation failed (attempt {retry_count}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * self._retry_config['backoff_factor'], self._retry_config['max_delay'])
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi sự kiện tới Redis channel với retry logic."""
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        
        try:
            # Serialize payload to JSON
            message = json.dumps(payload)
            
            # Publish với retry logic
            def _publish_operation():
                published = self._redis_client.publish(topic, message)
                if published == 0:
                    self._logger.warning(f"No subscribers for topic '{topic}'")
                return published
            
            self._retry_operation(_publish_operation)
            self._logger.debug(f"Published message to topic '{topic}': {payload}")
            
        except Exception as e:
            self._logger.error(f"Failed to publish message to topic '{topic}': {e}")
            raise
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho Redis channel."""
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
                
                # Subscribe to Redis channel if first subscriber
                if len(self._subscribers[topic]) == 1:
                    try:
                        self._pubsub.subscribe(topic)
                        self._logger.debug(f"Subscribed to Redis channel '{topic}'")
                    except Exception as e:
                        self._logger.error(f"Failed to subscribe to Redis channel '{topic}': {e}")
                        raise
    
    def start_listening(self) -> None:
        """Khởi động background listener thread."""
        if self._listener_thread and self._listener_thread.is_alive():
            self._logger.warning("Listener thread already running")
            return
        
        self._stop_listening = False
        self._listener_thread = threading.Thread(target=self._listen_for_messages, daemon=True)
        self._listener_thread.start()
        self._logger.info("Redis listener thread started")
    
    def _listen_for_messages(self) -> None:
        """Background thread để lắng nghe Redis messages."""
        try:
            while not self._stop_listening:
                try:
                    # Non-blocking get message with timeout
                    message = self._pubsub.get_message(timeout=1.0)
                    
                    if message and message['type'] == 'message':
                        topic = message['channel']
                        data = message['data']
                        
                        try:
                            # Deserialize JSON payload
                            payload = json.loads(data)
                            
                            # Call all subscribers for this topic
                            callbacks = []
                            with self._lock:
                                callbacks = list(self._subscribers.get(topic, []))
                            
                            for callback in callbacks:
                                try:
                                    callback(payload)
                                except Exception as e:
                                    self._logger.error(f"Error calling callback for topic '{topic}': {e}")
                                    
                        except json.JSONDecodeError as e:
                            self._logger.error(f"Invalid JSON in message from topic '{topic}': {e}")
                            
                except Exception as e:
                    if not self._stop_listening:
                        self._logger.error(f"Error in Redis listener: {e}")
                        time.sleep(1)  # Avoid tight loop on persistent errors
                        
        except Exception as e:
            self._logger.error(f"Fatal error in Redis listener thread: {e}")
    
    def stop(self) -> None:
        """Dừng Redis backend và cleanup resources."""
        self._stop_listening = True
        
        # Wait for listener thread to finish
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5.0)
            if self._listener_thread.is_alive():
                self._logger.warning("Listener thread did not stop gracefully")
        
        # Close pubsub connection
        if self._pubsub:
            try:
                self._pubsub.close()
            except Exception as e:
                self._logger.error(f"Error closing pubsub connection: {e}")
        
        # Close Redis client
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception as e:
                self._logger.error(f"Error closing Redis client: {e}")
        
        # Clear subscribers
        with self._lock:
            self._subscribers.clear()
        
        self._logger.info("Redis backend stopped")


class RabbitMQEventBusBackend(EventBusBackend):
    """Backend driver cho EventBus sử dụng RabbitMQ với High Availability."""
    
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._connection = None
        self._channel = None
        self._listener_thread = None
        self._stop_listening = False
        self._lock = threading.RLock()
        self._subscribers: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._consumer_tags = {}
        
        # RabbitMQ connection configuration
        self._rabbitmq_config = {
            'host': os.getenv('RABBITMQ_HOST', 'localhost'),
            'port': int(os.getenv('RABBITMQ_PORT', '5672')),
            'virtual_host': os.getenv('RABBITMQ_VHOST', '/mining'),
            'username': os.getenv('RABBITMQ_USER', 'mining-user'),
            'password': os.getenv('RABBITMQ_PASSWORD', 'mining-password'),
            'connection_attempts': 5,
            'retry_delay': 5,
            'socket_timeout': 10,
            'heartbeat': 60,
            'blocked_connection_timeout': 300,
        }
        
        # Exchange and routing configuration
        self._exchange_config = {
            'name': 'mining',
            'type': 'topic',
            'durable': True,
            'auto_delete': False,
        }
        
        # Retry configuration
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 0.1,
            'max_delay': 5.0,
            'backoff_factor': 2.0
        }
        
        # Initialize RabbitMQ connection
        self._initialize_rabbitmq()
    
    def _initialize_rabbitmq(self) -> None:
        """Khởi tạo kết nối RabbitMQ với retry logic và HA support."""
        try:
            import pika
            
            # Connection parameters với HA support
            connection_params = pika.ConnectionParameters(
                host=self._rabbitmq_config['host'],
                port=self._rabbitmq_config['port'],
                virtual_host=self._rabbitmq_config['virtual_host'],
                credentials=pika.PlainCredentials(
                    self._rabbitmq_config['username'],
                    self._rabbitmq_config['password']
                ),
                connection_attempts=self._rabbitmq_config['connection_attempts'],
                retry_delay=self._rabbitmq_config['retry_delay'],
                socket_timeout=self._rabbitmq_config['socket_timeout'],
                heartbeat=self._rabbitmq_config['heartbeat'],
                blocked_connection_timeout=self._rabbitmq_config['blocked_connection_timeout']
            )
            
            # Establish connection
            self._connection = pika.BlockingConnection(connection_params)
            self._channel = self._connection.channel()
            
            # Declare exchange
            self._channel.exchange_declare(
                exchange=self._exchange_config['name'],
                exchange_type=self._exchange_config['type'],
                durable=self._exchange_config['durable'],
                auto_delete=self._exchange_config['auto_delete']
            )
            
            self._logger.info("RabbitMQ connection established successfully")
            
        except ImportError:
            raise ImportError("Pika package not installed. Run: pip install pika>=1.3.0")
        except Exception as e:
            self._logger.error(f"Failed to initialize RabbitMQ connection: {e}")
            raise
    
    def _retry_operation(self, operation, *args, **kwargs):
        """Retry logic cho RabbitMQ operations với exponential backoff."""
        retry_count = 0
        delay = self._retry_config['base_delay']
        
        while retry_count < self._retry_config['max_retries']:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                retry_count += 1
                if retry_count >= self._retry_config['max_retries']:
                    self._logger.error(f"RabbitMQ operation failed after {retry_count} retries: {e}")
                    raise
                
                self._logger.warning(f"RabbitMQ operation failed (attempt {retry_count}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * self._retry_config['backoff_factor'], self._retry_config['max_delay'])
                
                # Reconnect if connection is broken
                if not self._connection or self._connection.is_closed:
                    self._initialize_rabbitmq()
    
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Gửi message tới RabbitMQ topic với retry logic và message durability."""
        if not self._connection or self._connection.is_closed:
            raise RuntimeError("RabbitMQ connection not initialized")
        
        try:
            # Serialize payload to JSON
            message_body = json.dumps(payload)
            
            # Publish với retry logic và message durability
            def _publish_operation():
                import pika
                
                self._channel.basic_publish(
                    exchange=self._exchange_config['name'],
                    routing_key=topic,
                    body=message_body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Message durability
                        content_type='application/json',
                        timestamp=int(time.time()),
                        message_id=f"{topic}-{int(time.time())}-{os.getpid()}"
                    )
                )
            
            self._retry_operation(_publish_operation)
            self._logger.debug(f"Published message to topic '{topic}': {payload}")
            
        except Exception as e:
            self._logger.error(f"Failed to publish message to topic '{topic}': {e}")
            raise
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Đăng ký callback cho RabbitMQ topic với durable queue."""
        with self._lock:
            if callback not in self._subscribers[topic]:
                self._subscribers[topic].append(callback)
                
                # Declare durable queue for topic if first subscriber
                if len(self._subscribers[topic]) == 1:
                    try:
                        queue_name = topic.replace(':', '.')
                        
                        # Declare durable queue
                        self._channel.queue_declare(
                            queue=queue_name,
                            durable=True,
                            auto_delete=False
                        )
                        
                        # Bind queue to exchange
                        self._channel.queue_bind(
                            exchange=self._exchange_config['name'],
                            queue=queue_name,
                            routing_key=topic
                        )
                        
                        self._logger.debug(f"Declared and bound queue '{queue_name}' for topic '{topic}'")
                        
                    except Exception as e:
                        self._logger.error(f"Failed to setup queue for topic '{topic}': {e}")
                        raise
    
    def start_listening(self) -> None:
        """Khởi động background listener thread với consumer acknowledgment."""
        if self._listener_thread and self._listener_thread.is_alive():
            self._logger.warning("Listener thread already running")
            return
        
        self._stop_listening = False
        self._listener_thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._listener_thread.start()
        self._logger.info("RabbitMQ listener thread started")
    
    def _consume_messages(self) -> None:
        """Background thread để consume RabbitMQ messages với ACK."""
        try:
            # Setup consumers for all subscribed topics
            for topic in self._subscribers.keys():
                queue_name = topic.replace(':', '.')
                
                def make_callback(topic_name):
                    def callback(ch, method, properties, body):
                        try:
                            # Deserialize JSON payload
                            payload = json.loads(body.decode('utf-8'))
                            
                            # Call all subscribers for this topic
                            callbacks = []
                            with self._lock:
                                callbacks = list(self._subscribers.get(topic_name, []))
                            
                            for callback_func in callbacks:
                                try:
                                    callback_func(payload)
                                except Exception as e:
                                    self._logger.error(f"Error calling callback for topic '{topic_name}': {e}")
                            
                            # Acknowledge message after successful processing
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                            
                        except json.JSONDecodeError as e:
                            self._logger.error(f"Invalid JSON in message from topic '{topic_name}': {e}")
                            # Reject message with no requeue
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                        except Exception as e:
                            self._logger.error(f"Error processing message from topic '{topic_name}': {e}")
                            # Reject message with requeue for retry
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    
                    return callback
                
                # Setup consumer with manual acknowledgment
                consumer_tag = self._channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=make_callback(topic),
                    auto_ack=False  # Manual acknowledgment for message durability
                )
                
                self._consumer_tags[topic] = consumer_tag
                self._logger.debug(f"Started consuming queue '{queue_name}' for topic '{topic}'")
            
            # Start consuming (blocking)
            self._channel.start_consuming()
            
        except Exception as e:
            if not self._stop_listening:
                self._logger.error(f"Error in RabbitMQ consumer thread: {e}")
    
    def stop(self) -> None:
        """Dừng RabbitMQ backend và cleanup resources."""
        self._stop_listening = True
        
        # Stop consuming
        if self._channel and not self._channel.is_closed:
            try:
                self._channel.stop_consuming()
                
                # Cancel consumers
                for topic, consumer_tag in self._consumer_tags.items():
                    self._channel.basic_cancel(consumer_tag)
                    self._logger.debug(f"Cancelled consumer for topic '{topic}'")
                
            except Exception as e:
                self._logger.error(f"Error stopping consumers: {e}")
        
        # Wait for listener thread to finish
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5.0)
            if self._listener_thread.is_alive():
                self._logger.warning("Listener thread did not stop gracefully")
        
        # Close connection
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.close()
            except Exception as e:
                self._logger.error(f"Error closing RabbitMQ connection: {e}")
        
        # Clear subscribers
        with self._lock:
            self._subscribers.clear()
            self._consumer_tags.clear()
        
        self._logger.info("RabbitMQ backend stopped")


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
            "rabbitmq": RabbitMQEventBusBackend,
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