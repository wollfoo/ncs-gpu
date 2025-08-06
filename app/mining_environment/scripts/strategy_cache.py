"""
✅ INTELLIGENT STRATEGY CACHE SYSTEM
Advanced caching với intelligent eviction, metrics tracking, và hash-based optimization
cho mining environment strategy management.
"""

import time
import hashlib
import threading
from typing import Dict, Any, Optional, Tuple, List, Set
from dataclasses import dataclass, field
from enum import Enum
import json
from collections import defaultdict, OrderedDict

# Import unified logging và error management
try:
    from .module_loggers import get_gpu_cloaking_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity
except ImportError:
    from module_loggers import get_gpu_cloaking_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity

class CacheEvictionPolicy(Enum):
    """✅ CACHE POLICIES: Các chính sách eviction cho strategy cache"""
    LRU = "least_recently_used"      # Least Recently Used - loại bỏ item ít được sử dụng gần đây nhất
    LFU = "least_frequently_used"    # Least Frequently Used - loại bỏ item ít được sử dụng thường xuyên nhất
    TTL = "time_to_live"             # Time To Live - loại bỏ item dựa trên thời gian sống
    SIZE = "size_based"              # Size-based - loại bỏ khi cache đạt size limit
    INTELLIGENT = "intelligent"      # Intelligent - kết hợp multiple factors

@dataclass
class CacheEntry:
    """✅ CACHE ENTRY: Detailed cache entry với comprehensive metadata"""
    
    strategy_object: Any                              # Actual strategy instance
    cache_key: str                                   # Unique cache identifier
    creation_time: float = field(default_factory=time.time)
    last_access_time: float = field(default_factory=time.time)
    access_count: int = 0                            # Number of times accessed
    hit_count: int = 0                               # Successful cache hits
    process_type: str = ""                           # Process type that created this entry
    strategy_type: str = ""                          # Type of strategy (CPU, GPU, etc.)
    size_estimate: int = 0                           # Estimated memory usage in bytes
    creation_cost_ms: float = 0.0                    # Time taken to create strategy (ms)
    last_validation_time: float = 0.0                # Last time entry was validated
    validation_success: bool = True                  # Whether last validation was successful
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if cache entry has expired based on TTL"""
        return (time.time() - self.creation_time) > ttl_seconds
    
    def calculate_priority_score(self) -> float:
        """
        ✅ INTELLIGENT SCORING: Calculate priority score cho intelligent eviction.
        Higher score = higher priority (less likely to be evicted)
        """
        now = time.time()
        
        # ✅ RECENCY FACTOR: Recent access gets higher priority
        recency_score = 1.0 / max(1.0, (now - self.last_access_time) / 3600)  # Hours since last access
        
        # ✅ FREQUENCY FACTOR: More frequently used gets higher priority
        frequency_score = min(10.0, self.access_count / 10.0)  # Cap at 10
        
        # ✅ CREATION COST FACTOR: Expensive-to-create items get higher priority
        cost_score = min(5.0, self.creation_cost_ms / 1000.0)  # Creation cost in seconds
        
        # ✅ SUCCESS RATE FACTOR: Successful entries get higher priority
        success_score = 1.0 if self.validation_success else 0.1
        
        # ✅ COMBINED SCORE: Weighted combination
        return (recency_score * 0.3 + frequency_score * 0.4 + cost_score * 0.2 + success_score * 0.1)

@dataclass 
class CacheMetrics:
    """✅ CACHE METRICS: Comprehensive cache performance metrics"""
    
    total_requests: int = 0                          # Total cache requests
    cache_hits: int = 0                              # Successful cache hits
    cache_misses: int = 0                            # Cache misses
    evictions: int = 0                               # Number of evictions performed
    total_entries: int = 0                           # Current number of entries
    memory_usage_bytes: int = 0                      # Estimated memory usage
    average_creation_time_ms: float = 0.0            # Average strategy creation time
    hit_rate: float = 0.0                            # Cache hit rate percentage
    
    # ✅ TIME-BASED METRICS: Performance over time
    recent_hit_rates: List[float] = field(default_factory=list)  # Hit rates over time windows
    eviction_by_policy: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    strategy_type_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(dict))
    
    def update_hit_rate(self) -> None:
        """Update calculated hit rate"""
        if self.total_requests > 0:
            self.hit_rate = (self.cache_hits / self.total_requests) * 100.0
        else:
            self.hit_rate = 0.0
    
    def add_time_window_hit_rate(self) -> None:
        """Add current hit rate to time window tracking"""
        self.recent_hit_rates.append(self.hit_rate)
        # Keep only last 24 time windows (hours)
        if len(self.recent_hit_rates) > 24:
            self.recent_hit_rates.pop(0)

class IntelligentStrategyCache:
    """
    ✅ INTELLIGENT CACHE: Advanced strategy cache với comprehensive optimization.
    
    Features:
    - Hash-based cache keys cho efficient lookups
    - Multiple eviction policies (LRU, LFU, TTL, Intelligent)
    - Comprehensive metrics tracking
    - Thread-safe operations
    - Automatic cache validation và cleanup
    - Memory usage monitoring
    """
    
    def __init__(
        self, 
        max_size: int = 1000,
        default_ttl_seconds: float = 3600.0,  # 1 hour
        eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.INTELLIGENT,
        enable_metrics: bool = True
    ):
        """Initialize intelligent strategy cache"""
        
        # ✅ CONFIGURATION
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self.eviction_policy = eviction_policy
        self.enable_metrics = enable_metrics
        
        # ✅ STORAGE: Thread-safe cache storage
        self._cache: Dict[str, CacheEntry] = OrderedDict()
        self._access_order: Dict[str, float] = {}  # For LRU tracking
        self._cache_lock = threading.RLock()
        
        # ✅ METRICS: Performance tracking
        self.metrics = CacheMetrics()
        self.metrics_lock = threading.RLock()
        
        # ✅ LOGGING: Unified logging integration
        self.logger = get_gpu_cloaking_logger()
        self.error_reporter = get_error_reporter()
        
        # ✅ BACKGROUND TASKS: Cleanup and validation
        self._cleanup_interval = 300.0  # 5 minutes
        self._last_cleanup = time.time()
        self._validation_interval = 1800.0  # 30 minutes
        self._last_validation = time.time()
        
        self.logger.info("✅ [StrategyCache] Intelligent strategy cache initialized")
        self.logger.info(f"📊 [StrategyCache] Config: max_size={max_size}, ttl={default_ttl_seconds}s, policy={eviction_policy.value}")
    
    def _generate_cache_key(
        self, 
        strategy_type: str, 
        process_type: str, 
        config_hash: Optional[str] = None,
        strategy_hints: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        ✅ HASH-BASED KEY GENERATION: Generate optimized cache key với hash approach.
        
        :param strategy_type: Type of strategy (CPU, GPU, etc.)
        :param process_type: Process classification type
        :param config_hash: Optional configuration hash
        :param strategy_hints: Optional strategy hints dictionary
        :return: Optimized cache key string
        """
        try:
            # ✅ BASE COMPONENTS: Core cache key components
            key_components = [
                f"strategy:{strategy_type}",
                f"process:{process_type}"
            ]
            
            # ✅ CONFIG HASH: Include configuration if provided
            if config_hash:
                key_components.append(f"config:{config_hash}")
            
            # ✅ STRATEGY HINTS: Include hints hash if provided
            if strategy_hints:
                hints_json = json.dumps(strategy_hints, sort_keys=True)
                hints_hash = hashlib.md5(hints_json.encode()).hexdigest()[:8]
                key_components.append(f"hints:{hints_hash}")
            
            # ✅ COMBINED KEY: Create combined key string
            combined_key = "|".join(key_components)
            
            # ✅ HASH OPTIMIZATION: Generate final hash-based key
            final_hash = hashlib.sha256(combined_key.encode()).hexdigest()[:16]
            readable_key = f"{strategy_type}_{process_type}_{final_hash}"
            
            return readable_key
            
        except Exception as e:
            # ✅ FALLBACK: Simple key generation on error
            self.error_reporter.report_error(
                ErrorCode.INTERNAL_ERROR,
                f"Cache key generation failed: {e}",
                ErrorSeverity.LOW,
                module='strategy_cache',
                function='_generate_cache_key',
                context_data={'strategy_type': strategy_type, 'process_type': process_type}
            )
            return f"{strategy_type}_{process_type}_{int(time.time())}"
    
    def get(
        self, 
        strategy_type: str, 
        process_type: str, 
        config_hash: Optional[str] = None,
        strategy_hints: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        ✅ CACHE GET: Retrieve strategy from cache với intelligent tracking.
        
        :param strategy_type: Type of strategy to retrieve
        :param process_type: Process type classification
        :param config_hash: Configuration hash for validation
        :param strategy_hints: Strategy hints for key generation
        :return: Cached strategy object or None if not found
        """
        cache_key = self._generate_cache_key(strategy_type, process_type, config_hash, strategy_hints)
        
        with self._cache_lock:
            # ✅ METRICS: Update request count
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.total_requests += 1
            
            # ✅ CACHE LOOKUP: Check if entry exists
            if cache_key not in self._cache:
                if self.enable_metrics:
                    with self.metrics_lock:
                        self.metrics.cache_misses += 1
                        self.metrics.update_hit_rate()
                
                self.logger.debug(f"❌ [StrategyCache] Cache miss: {cache_key}")
                return None
            
            entry = self._cache[cache_key]
            
            # ✅ TTL VALIDATION: Check if entry has expired
            if entry.is_expired(self.default_ttl):
                self.logger.debug(f"⏰ [StrategyCache] Cache entry expired: {cache_key}")
                del self._cache[cache_key]
                if cache_key in self._access_order:
                    del self._access_order[cache_key]
                
                if self.enable_metrics:
                    with self.metrics_lock:
                        self.metrics.cache_misses += 1
                        self.metrics.evictions += 1
                        self.metrics.eviction_by_policy['TTL'] += 1
                        self.metrics.update_hit_rate()
                
                return None
            
            # ✅ CACHE HIT: Update access tracking
            entry.last_access_time = time.time()
            entry.access_count += 1
            entry.hit_count += 1
            
            self._access_order[cache_key] = entry.last_access_time
            
            # Move to end for LRU ordering
            self._cache.move_to_end(cache_key)
            
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.cache_hits += 1
                    self.metrics.update_hit_rate()
            
            self.logger.debug(f"✅ [StrategyCache] Cache hit: {cache_key} (access_count: {entry.access_count})")
            return entry.strategy_object
    
    def put(
        self, 
        strategy_type: str, 
        process_type: str, 
        strategy_object: Any,
        creation_time_ms: float = 0.0,
        config_hash: Optional[str] = None,
        strategy_hints: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        ✅ CACHE PUT: Store strategy in cache với intelligent management.
        
        :param strategy_type: Type of strategy being cached
        :param process_type: Process type classification
        :param strategy_object: Strategy instance to cache
        :param creation_time_ms: Time taken to create strategy (for metrics)
        :param config_hash: Configuration hash for validation
        :param strategy_hints: Strategy hints for key generation
        :param metadata: Additional metadata for cache entry
        :return: Generated cache key
        """
        cache_key = self._generate_cache_key(strategy_type, process_type, config_hash, strategy_hints)
        
        with self._cache_lock:
            # ✅ EVICTION CHECK: Ensure cache doesn't exceed max size
            if len(self._cache) >= self.max_size:
                self._evict_entries()
            
            # ✅ CREATE ENTRY: Create comprehensive cache entry
            now = time.time()
            entry = CacheEntry(
                strategy_object=strategy_object,
                cache_key=cache_key,
                creation_time=now,
                last_access_time=now,
                access_count=1,
                process_type=process_type,
                strategy_type=strategy_type,
                creation_cost_ms=creation_time_ms,
                last_validation_time=now,
                metadata=metadata or {}
            )
            
            # ✅ ESTIMATE SIZE: Try to estimate memory usage
            try:
                import sys
                entry.size_estimate = sys.getsizeof(strategy_object)
            except:
                entry.size_estimate = 1024  # Default 1KB estimate
            
            # ✅ STORE ENTRY: Add to cache
            self._cache[cache_key] = entry
            self._access_order[cache_key] = now
            
            # ✅ METRICS UPDATE: Update cache metrics
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.total_entries = len(self._cache)
                    self.metrics.memory_usage_bytes += entry.size_estimate
                    
                    # Update average creation time
                    if creation_time_ms > 0:
                        total_time = self.metrics.average_creation_time_ms * (self.metrics.total_entries - 1)
                        self.metrics.average_creation_time_ms = (total_time + creation_time_ms) / self.metrics.total_entries
            
            self.logger.debug(f"📝 [StrategyCache] Cached strategy: {cache_key} (size: {entry.size_estimate} bytes)")
            return cache_key
    
    def _evict_entries(self) -> None:
        """
        ✅ INTELLIGENT EVICTION: Remove entries based on configured eviction policy.
        """
        try:
            entries_to_remove = max(1, int(self.max_size * 0.1))  # Remove 10% when full
            
            if self.eviction_policy == CacheEvictionPolicy.LRU:
                self._evict_lru(entries_to_remove)
            elif self.eviction_policy == CacheEvictionPolicy.LFU:
                self._evict_lfu(entries_to_remove)
            elif self.eviction_policy == CacheEvictionPolicy.TTL:
                self._evict_expired()
            elif self.eviction_policy == CacheEvictionPolicy.INTELLIGENT:
                self._evict_intelligent(entries_to_remove)
            else:
                self._evict_lru(entries_to_remove)  # Default fallback
                
        except Exception as e:
            self.error_reporter.report_error(
                ErrorCode.INTERNAL_ERROR,
                f"Cache eviction failed: {e}",
                ErrorSeverity.MEDIUM,
                module='strategy_cache',
                function='_evict_entries'
            )
    
    def _evict_lru(self, count: int) -> None:
        """Remove least recently used entries"""
        sorted_keys = sorted(self._access_order.items(), key=lambda x: x[1])
        for i in range(min(count, len(sorted_keys))):
            key_to_remove = sorted_keys[i][0]
            if key_to_remove in self._cache:
                entry = self._cache[key_to_remove]
                del self._cache[key_to_remove]
                del self._access_order[key_to_remove]
                
                if self.enable_metrics:
                    with self.metrics_lock:
                        self.metrics.evictions += 1
                        self.metrics.eviction_by_policy['LRU'] += 1
                        self.metrics.memory_usage_bytes -= entry.size_estimate
                
                self.logger.debug(f"🗑️ [StrategyCache] LRU evicted: {key_to_remove}")
    
    def _evict_lfu(self, count: int) -> None:
        """Remove least frequently used entries"""
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].access_count)
        for i in range(min(count, len(sorted_entries))):
            key_to_remove = sorted_entries[i][0]
            entry = self._cache[key_to_remove]
            del self._cache[key_to_remove]
            if key_to_remove in self._access_order:
                del self._access_order[key_to_remove]
            
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.evictions += 1
                    self.metrics.eviction_by_policy['LFU'] += 1
                    self.metrics.memory_usage_bytes -= entry.size_estimate
            
            self.logger.debug(f"🗑️ [StrategyCache] LFU evicted: {key_to_remove}")
    
    def _evict_expired(self) -> None:
        """Remove expired entries"""
        expired_keys = []
        for key, entry in self._cache.items():
            if entry.is_expired(self.default_ttl):
                expired_keys.append(key)
        
        for key in expired_keys:
            entry = self._cache[key]
            del self._cache[key]
            if key in self._access_order:
                del self._access_order[key]
            
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.evictions += 1
                    self.metrics.eviction_by_policy['TTL'] += 1
                    self.metrics.memory_usage_bytes -= entry.size_estimate
            
            self.logger.debug(f"🗑️ [StrategyCache] TTL evicted: {key}")
    
    def _evict_intelligent(self, count: int) -> None:
        """Remove entries using intelligent priority scoring"""
        # Calculate priority scores for all entries
        scored_entries = []
        for key, entry in self._cache.items():
            priority_score = entry.calculate_priority_score()
            scored_entries.append((key, priority_score))
        
        # Sort by priority score (ascending - lowest priority first)
        scored_entries.sort(key=lambda x: x[1])
        
        # Remove lowest priority entries
        for i in range(min(count, len(scored_entries))):
            key_to_remove = scored_entries[i][0]
            entry = self._cache[key_to_remove]
            del self._cache[key_to_remove]
            if key_to_remove in self._access_order:
                del self._access_order[key_to_remove]
            
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.evictions += 1
                    self.metrics.eviction_by_policy['INTELLIGENT'] += 1
                    self.metrics.memory_usage_bytes -= entry.size_estimate
            
            priority_score = scored_entries[i][1]
            self.logger.debug(f"🗑️ [StrategyCache] Intelligent evicted: {key_to_remove} (priority: {priority_score:.3f})")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        ✅ METRICS RETRIEVAL: Get comprehensive cache performance metrics.
        
        :return: Dictionary containing detailed cache metrics
        """
        with self.metrics_lock:
            return {
                'timestamp': time.time(),
                'cache_performance': {
                    'total_requests': self.metrics.total_requests,
                    'cache_hits': self.metrics.cache_hits,
                    'cache_misses': self.metrics.cache_misses,
                    'hit_rate_percent': round(self.metrics.hit_rate, 2),
                    'total_entries': len(self._cache),
                    'max_size': self.max_size,
                    'memory_usage_mb': round(self.metrics.memory_usage_bytes / (1024 * 1024), 2),
                    'average_creation_time_ms': round(self.metrics.average_creation_time_ms, 2)
                },
                'eviction_stats': {
                    'total_evictions': self.metrics.evictions,
                    'eviction_by_policy': dict(self.metrics.eviction_by_policy),
                    'eviction_policy': self.eviction_policy.value
                },
                'time_series': {
                    'recent_hit_rates': self.metrics.recent_hit_rates[-10:],  # Last 10 windows
                },
                'configuration': {
                    'max_size': self.max_size,
                    'default_ttl_seconds': self.default_ttl,
                    'eviction_policy': self.eviction_policy.value,
                    'metrics_enabled': self.enable_metrics
                }
            }
    
    def clear(self) -> int:
        """
        ✅ CACHE CLEAR: Clear all cache entries và reset metrics.
        
        :return: Number of entries removed
        """
        with self._cache_lock:
            entries_removed = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            
            if self.enable_metrics:
                with self.metrics_lock:
                    self.metrics.memory_usage_bytes = 0
                    self.metrics.total_entries = 0
            
            self.logger.info(f"🧹 [StrategyCache] Cache cleared: {entries_removed} entries removed")
            return entries_removed
    
    def validate_cache(self) -> Dict[str, Any]:
        """
        ✅ CACHE VALIDATION: Validate all cache entries và remove invalid ones.
        
        :return: Validation results dictionary
        """
        validation_start = time.time()
        valid_entries = 0
        invalid_entries = 0
        removed_entries = []
        
        with self._cache_lock:
            entries_to_remove = []
            
            for key, entry in self._cache.items():
                try:
                    # ✅ BASIC VALIDATION: Check if strategy object still exists and is valid
                    if entry.strategy_object is None:
                        entries_to_remove.append(key)
                        invalid_entries += 1
                        continue
                    
                    # ✅ TTL VALIDATION: Check expiration
                    if entry.is_expired(self.default_ttl):
                        entries_to_remove.append(key)
                        invalid_entries += 1
                        continue
                    
                    # ✅ OBJECT VALIDATION: Basic object integrity check
                    if hasattr(entry.strategy_object, '__class__'):
                        entry.last_validation_time = time.time()
                        entry.validation_success = True
                        valid_entries += 1
                    else:
                        entries_to_remove.append(key)
                        invalid_entries += 1
                    
                except Exception as e:
                    entries_to_remove.append(key)
                    invalid_entries += 1
                    entry.validation_success = False
            
            # ✅ REMOVE INVALID ENTRIES
            for key in entries_to_remove:
                if key in self._cache:
                    entry = self._cache[key]
                    removed_entries.append({
                        'key': key,
                        'strategy_type': entry.strategy_type,
                        'process_type': entry.process_type,
                        'age_seconds': time.time() - entry.creation_time
                    })
                    
                    if self.enable_metrics:
                        with self.metrics_lock:
                            self.metrics.memory_usage_bytes -= entry.size_estimate
                    
                    del self._cache[key]
                    if key in self._access_order:
                        del self._access_order[key]
        
        validation_time_ms = (time.time() - validation_start) * 1000
        
        validation_result = {
            'timestamp': time.time(),
            'validation_time_ms': round(validation_time_ms, 2),
            'valid_entries': valid_entries,
            'invalid_entries': invalid_entries,
            'removed_entries': removed_entries,
            'total_entries_after': len(self._cache),
            'cache_health_score': (valid_entries / max(1, valid_entries + invalid_entries)) * 100
        }
        
        self.logger.info(f"🔍 [StrategyCache] Cache validation completed: "
                        f"{valid_entries} valid, {invalid_entries} invalid, "
                        f"health score: {validation_result['cache_health_score']:.1f}%")
        
        return validation_result


# ✅ GLOBAL INSTANCE: Create singleton cache instance
_global_strategy_cache: Optional[IntelligentStrategyCache] = None
_cache_lock = threading.RLock()

def get_strategy_cache(
    max_size: int = 1000,
    ttl_seconds: float = 3600.0,
    eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.INTELLIGENT
) -> IntelligentStrategyCache:
    """
    ✅ CONVENIENCE FUNCTION: Get global strategy cache instance.
    
    :param max_size: Maximum cache size
    :param ttl_seconds: Default TTL for cache entries
    :param eviction_policy: Eviction policy to use
    :return: IntelligentStrategyCache instance
    """
    global _global_strategy_cache
    
    with _cache_lock:
        if _global_strategy_cache is None:
            _global_strategy_cache = IntelligentStrategyCache(
                max_size=max_size,
                default_ttl_seconds=ttl_seconds,
                eviction_policy=eviction_policy
            )
        return _global_strategy_cache

def get_cache_metrics() -> Dict[str, Any]:
    """
    ✅ CONVENIENCE FUNCTION: Get cache metrics from global instance.
    
    :return: Cache metrics dictionary
    """
    cache = get_strategy_cache()
    return cache.get_metrics()

def clear_strategy_cache() -> int:
    """
    ✅ CONVENIENCE FUNCTION: Clear global strategy cache.
    
    :return: Number of entries removed
    """
    cache = get_strategy_cache()
    return cache.clear()