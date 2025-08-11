#!/usr/bin/env python3
"""
strategies/selector.py - Strategy Selector (Bộ chọn chiến lược) cho GPU Optimization

Module này cung cấp logic để chọn chiến lược tối ưu phù hợp nhất dựa trên:
- Current system metrics (metrics hệ thống hiện tại)
- GPU utilization patterns (mẫu sử dụng GPU)
- Resource constraints (ràng buộc tài nguyên)
- Historical performance (hiệu suất lịch sử)

Production-ready với:
- Dynamic strategy selection (chọn chiến lược động)
- Multi-criteria decision making (ra quyết định đa tiêu chí)
- Fallback mechanisms (cơ chế dự phòng)
- Performance tracking (theo dõi hiệu suất)
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional, Type, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
import json
from pathlib import Path

# Import base classes và các strategies
from base import (
    BaseStrategy, 
    StrategyType, 
    Priority, 
    StrategyContext, 
    StrategyResult,
    StrategyProtocol
)

# Logger configuration
logger = logging.getLogger(__name__)


@dataclass
class SelectionCriteria:
    """
    Selection Criteria (Tiêu chí lựa chọn) - Các tiêu chí để chọn strategy
    
    Attributes:
        gpu_threshold: Ngưỡng GPU utilization để trigger aggressive strategy
        memory_threshold: Ngưỡng memory để trigger conservative strategy  
        temperature_threshold: Ngưỡng nhiệt độ để trigger cooling strategy
        power_limit: Giới hạn công suất
        performance_target: Mục tiêu hiệu suất tối thiểu
    """
    gpu_threshold: float = 80.0  # Percentage
    memory_threshold: float = 85.0  # Percentage
    temperature_threshold: float = 75.0  # Celsius
    power_limit: float = 300.0  # Watts
    performance_target: float = 60.0  # Min performance percentage
    
    # Weights cho multi-criteria scoring
    weights: Dict[str, float] = field(default_factory=lambda: {
        'gpu_utilization': 0.3,
        'memory_usage': 0.2,
        'temperature': 0.2,
        'power_consumption': 0.15,
        'historical_success': 0.15
    })


@dataclass
class StrategyScore:
    """
    Strategy Score (Điểm chiến lược) - Điểm số và metadata cho strategy selection
    """
    strategy_type: StrategyType
    score: float
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-100%
    
    def __lt__(self, other):
        """For sorting - higher score is better"""
        return self.score < other.score


class SelectionMode(Enum):
    """
    Selection Mode (Chế độ chọn) - Các chế độ chọn strategy khác nhau
    """
    AUTOMATIC = "automatic"  # Tự động dựa trên metrics
    MANUAL = "manual"  # Chọn thủ công
    ROUND_ROBIN = "round_robin"  # Luân phiên
    WEIGHTED_RANDOM = "weighted_random"  # Ngẫu nhiên có trọng số
    LEARNING = "learning"  # Học từ lịch sử


class StrategySelector:
    """
    Strategy Selector (Bộ chọn chiến lược) - Chọn strategy tối ưu cho context
    
    Features:
    - Multi-criteria decision making dựa trên weighted scoring
    - Historical performance tracking
    - Dynamic threshold adjustment
    - Fallback strategies khi primary strategy fail
    """
    
    def __init__(self,
                 criteria: Optional[SelectionCriteria] = None,
                 mode: SelectionMode = SelectionMode.AUTOMATIC,
                 history_size: int = 100):
        """
        Initialize strategy selector
        
        Args:
            criteria: Tiêu chí chọn strategy
            mode: Chế độ selection
            history_size: Số lượng selections lưu trong history
        """
        self.criteria = criteria or SelectionCriteria()
        self.mode = mode
        self.history_size = history_size
        
        # Strategy registry
        self.available_strategies: Dict[StrategyType, Type[BaseStrategy]] = {}
        
        # Performance history
        self.selection_history: List[Dict[str, Any]] = []
        self.performance_stats: Dict[StrategyType, Dict[str, float]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Cache cho recent selections
        self._selection_cache: Dict[str, Tuple[StrategyType, float]] = {}
        self._cache_ttl = 10.0  # seconds
        
        # Round-robin state
        self._round_robin_index = 0
        
        logger.info(f"Initialized StrategySelector [mode={mode.value}]")
    
    def register_strategy(self, 
                         strategy_type: StrategyType,
                         strategy_class: Type[BaseStrategy]):
        """
        Register strategy (Đăng ký chiến lược) vào selector
        
        Args:
            strategy_type: Loại strategy
            strategy_class: Class implementation của strategy
        """
        with self._lock:
            self.available_strategies[strategy_type] = strategy_class
            
            # Initialize performance stats
            if strategy_type not in self.performance_stats:
                self.performance_stats[strategy_type] = {
                    'total_selections': 0,
                    'successful': 0,
                    'failed': 0,
                    'avg_improvement': 0.0,
                    'avg_duration': 0.0
                }
            
            logger.info(f"Registered strategy: {strategy_type.name}")
    
    def select_strategy(self, context: StrategyContext) -> Optional[StrategyType]:
        """
        Select optimal strategy (Chọn chiến lược tối ưu) cho context
        
        Main method để chọn strategy dựa trên mode và criteria.
        
        Args:
            context: Current context với metrics
            
        Returns:
            StrategyType được chọn, hoặc None nếu không có strategy phù hợp
        """
        with self._lock:
            # Check cache first
            cache_key = self._get_cache_key(context)
            if cache_key in self._selection_cache:
                cached_type, cached_time = self._selection_cache[cache_key]
                if time.time() - cached_time < self._cache_ttl:
                    logger.debug(f"Using cached selection: {cached_type.name}")
                    return cached_type
            
            # Select based on mode
            selected = None
            
            if self.mode == SelectionMode.AUTOMATIC:
                selected = self._select_automatic(context)
            elif self.mode == SelectionMode.MANUAL:
                selected = self._select_manual(context)
            elif self.mode == SelectionMode.ROUND_ROBIN:
                selected = self._select_round_robin()
            elif self.mode == SelectionMode.WEIGHTED_RANDOM:
                selected = self._select_weighted_random(context)
            elif self.mode == SelectionMode.LEARNING:
                selected = self._select_learning(context)
            
            if selected:
                # Update cache
                self._selection_cache[cache_key] = (selected, time.time())
                
                # Record selection
                self._record_selection(selected, context)
            
            return selected
    
    def _select_automatic(self, context: StrategyContext) -> Optional[StrategyType]:
        """
        Automatic selection (Chọn tự động) dựa trên scoring
        
        Tính điểm cho mỗi strategy và chọn strategy có điểm cao nhất.
        """
        scores = []
        
        for strategy_type in self.available_strategies.keys():
            score = self._calculate_strategy_score(strategy_type, context)
            scores.append(score)
        
        if not scores:
            logger.warning("No strategies available for scoring")
            return None
        
        # Sort by score (highest first)
        scores.sort(reverse=True)
        
        # Log top scores
        logger.info(f"Top strategy scores: {[(s.strategy_type.name, f'{s.score:.2f}') for s in scores[:3]]}")
        
        # Return best strategy
        best = scores[0]
        
        # Check confidence threshold
        if best.confidence < 50.0:
            logger.warning(f"Low confidence ({best.confidence:.1f}%) for {best.strategy_type.name}")
            # Use fallback strategy
            return StrategyType.BALANCED
        
        return best.strategy_type
    
    def _calculate_strategy_score(self, 
                                  strategy_type: StrategyType,
                                  context: StrategyContext) -> StrategyScore:
        """
        Calculate score (Tính điểm) cho strategy
        
        Multi-criteria scoring dựa trên:
        - Current metrics vs thresholds
        - Historical performance
        - Context suitability
        """
        score = 0.0
        reasons = []
        confidence = 50.0  # Base confidence
        
        # Extract metrics
        gpu_util = context.gpu_metrics.get('utilization', 0)
        gpu_memory = context.gpu_metrics.get('memory_percent', 0)
        gpu_temp = context.gpu_metrics.get('temperature', 0)
        
        # Score based on strategy type
        if strategy_type == StrategyType.AGGRESSIVE:
            # Aggressive good for high GPU utilization
            if gpu_util > self.criteria.gpu_threshold:
                score += 30
                reasons.append(f"High GPU utilization ({gpu_util:.1f}%)")
                confidence += 20
            
            # But bad for high temperature
            if gpu_temp > self.criteria.temperature_threshold:
                score -= 20
                reasons.append(f"Temperature too high ({gpu_temp:.1f}°C)")
                confidence -= 10
        
        elif strategy_type == StrategyType.BALANCED:
            # Balanced is general purpose - always decent score
            score += 20
            reasons.append("General purpose strategy")
            
            # Better when metrics are moderate
            if 30 < gpu_util < 70:
                score += 15
                reasons.append("Moderate GPU utilization")
                confidence += 10
        
        elif strategy_type == StrategyType.CONSERVATIVE:
            # Conservative good for resource constraints
            if gpu_memory > self.criteria.memory_threshold:
                score += 25
                reasons.append(f"High memory usage ({gpu_memory:.1f}%)")
                confidence += 15
            
            if gpu_temp > self.criteria.temperature_threshold - 10:
                score += 20
                reasons.append("Temperature approaching threshold")
                confidence += 10
        
        elif strategy_type == StrategyType.CLOAK:
            # Cloak for stealth requirements
            if context.metadata.get('stealth_mode', False):
                score += 40
                reasons.append("Stealth mode enabled")
                confidence += 30
            
            # Also good for low activity periods
            if gpu_util < 20:
                score += 15
                reasons.append("Low activity period")
        
        # Add historical performance score
        hist_score = self._get_historical_score(strategy_type)
        score += hist_score * self.criteria.weights['historical_success']
        if hist_score > 0:
            reasons.append(f"Good historical performance ({hist_score:.1f})")
            confidence += min(hist_score / 2, 20)
        
        # Normalize confidence
        confidence = max(0, min(100, confidence))
        
        return StrategyScore(
            strategy_type=strategy_type,
            score=score,
            reasons=reasons,
            confidence=confidence
        )
    
    def _get_historical_score(self, strategy_type: StrategyType) -> float:
        """
        Get historical performance score (Lấy điểm hiệu suất lịch sử)
        
        Returns:
            Score 0-100 based on past performance
        """
        stats = self.performance_stats.get(strategy_type, {})
        
        if stats.get('total_selections', 0) == 0:
            return 50.0  # Neutral score for new strategies
        
        success_rate = (stats['successful'] / stats['total_selections']) * 100
        
        # Weight by number of selections (more data = more confidence)
        confidence_factor = min(stats['total_selections'] / 10, 1.0)
        
        return success_rate * confidence_factor
    
    def _select_round_robin(self) -> Optional[StrategyType]:
        """Round-robin selection (Chọn luân phiên)"""
        if not self.available_strategies:
            return None
        
        strategies = list(self.available_strategies.keys())
        selected = strategies[self._round_robin_index % len(strategies)]
        self._round_robin_index += 1
        
        return selected
    
    def _select_weighted_random(self, context: StrategyContext) -> Optional[StrategyType]:
        """Weighted random selection (Chọn ngẫu nhiên có trọng số)"""
        import random
        
        if not self.available_strategies:
            return None
        
        # Calculate weights based on scores
        weights = []
        strategies = []
        
        for strategy_type in self.available_strategies.keys():
            score = self._calculate_strategy_score(strategy_type, context)
            weights.append(max(score.score, 1))  # Ensure positive weight
            strategies.append(strategy_type)
        
        # Weighted random choice
        total_weight = sum(weights)
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for strategy, weight in zip(strategies, weights):
            cumulative += weight
            if r <= cumulative:
                return strategy
        
        return strategies[-1]  # Fallback
    
    def _select_manual(self, context: StrategyContext) -> Optional[StrategyType]:
        """Manual selection (Chọn thủ công) - uses metadata"""
        requested = context.metadata.get('requested_strategy')
        
        if requested and isinstance(requested, StrategyType):
            if requested in self.available_strategies:
                return requested
        
        # Fallback to automatic
        return self._select_automatic(context)
    
    def _select_learning(self, context: StrategyContext) -> Optional[StrategyType]:
        """
        Learning-based selection (Chọn dựa trên học tập)
        
        Uses reinforcement learning concepts to improve selection over time.
        """
        # For now, use automatic with boosted historical weights
        old_weight = self.criteria.weights['historical_success']
        self.criteria.weights['historical_success'] = 0.4  # Boost historical
        
        selected = self._select_automatic(context)
        
        # Restore weight
        self.criteria.weights['historical_success'] = old_weight
        
        return selected
    
    def _get_cache_key(self, context: StrategyContext) -> str:
        """Generate cache key from context"""
        # Simple hash based on key metrics
        key_parts = [
            str(context.pid),
            str(int(context.gpu_metrics.get('utilization', 0) / 10) * 10),  # Round to 10s
            str(int(context.gpu_metrics.get('temperature', 0) / 5) * 5),  # Round to 5s
        ]
        return "_".join(key_parts)
    
    def _record_selection(self, 
                         strategy_type: StrategyType,
                         context: StrategyContext):
        """Record selection for history"""
        record = {
            'timestamp': time.time(),
            'strategy_type': strategy_type.name,
            'context_summary': {
                'pid': context.pid,
                'gpu_util': context.gpu_metrics.get('utilization', 0),
                'gpu_temp': context.gpu_metrics.get('temperature', 0)
            }
        }
        
        self.selection_history.append(record)
        
        # Trim history
        if len(self.selection_history) > self.history_size:
            self.selection_history = self.selection_history[-self.history_size:]
        
        # Update stats
        stats = self.performance_stats[strategy_type]
        stats['total_selections'] += 1
    
    def update_performance(self,
                          strategy_type: StrategyType,
                          result: StrategyResult):
        """
        Update performance statistics (Cập nhật thống kê hiệu suất)
        
        Called after strategy execution to track performance.
        
        Args:
            strategy_type: Strategy that was executed
            result: Execution result
        """
        with self._lock:
            if strategy_type not in self.performance_stats:
                return
            
            stats = self.performance_stats[strategy_type]
            
            if result.success:
                stats['successful'] += 1
            else:
                stats['failed'] += 1
            
            # Update average duration
            n = stats['successful'] + stats['failed']
            stats['avg_duration'] = (
                (stats['avg_duration'] * (n - 1) + result.duration) / n
            )
            
            # Update average improvement
            gpu_improvement = result.get_improvement('gpu_utilization')
            if gpu_improvement is not None:
                stats['avg_improvement'] = (
                    (stats['avg_improvement'] * (n - 1) + gpu_improvement) / n
                )
    
    def get_recommendation(self, context: StrategyContext) -> Dict[str, Any]:
        """
        Get detailed recommendation (Lấy khuyến nghị chi tiết)
        
        Returns:
            Dictionary với strategy recommendation và reasoning
        """
        # Calculate scores for all strategies
        scores = []
        for strategy_type in self.available_strategies.keys():
            score = self._calculate_strategy_score(strategy_type, context)
            scores.append(score)
        
        scores.sort(reverse=True)
        
        if not scores:
            return {
                'recommended': None,
                'reason': 'No strategies available',
                'alternatives': []
            }
        
        return {
            'recommended': scores[0].strategy_type.name,
            'confidence': scores[0].confidence,
            'reasons': scores[0].reasons,
            'alternatives': [
                {
                    'strategy': s.strategy_type.name,
                    'score': s.score,
                    'confidence': s.confidence
                }
                for s in scores[1:4]  # Top 3 alternatives
            ],
            'mode': self.mode.value,
            'timestamp': time.time()
        }
    
    def export_statistics(self, filepath: Optional[Path] = None) -> Path:
        """
        Export statistics to JSON (Xuất thống kê ra JSON)
        
        Args:
            filepath: Optional custom filepath
            
        Returns:
            Path to exported file
        """
        if filepath is None:
            filepath = Path(f"strategy_selector_stats_{int(time.time())}.json")
        
        data = {
            'mode': self.mode.value,
            'performance_stats': {
                k.name: v for k, v in self.performance_stats.items()
            },
            'selection_history': self.selection_history[-50:],  # Last 50
            'criteria': {
                'gpu_threshold': self.criteria.gpu_threshold,
                'memory_threshold': self.criteria.memory_threshold,
                'temperature_threshold': self.criteria.temperature_threshold,
                'weights': self.criteria.weights
            },
            'timestamp': time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported statistics to {filepath}")
        return filepath
    
    def __repr__(self) -> str:
        return (f"StrategySelector(mode={self.mode.value}, "
                f"strategies={len(self.available_strategies)}, "
                f"history={len(self.selection_history)})")


# Export public API
__all__ = [
    'StrategySelector',
    'SelectionCriteria',
    'SelectionMode',
    'StrategyScore'
]
