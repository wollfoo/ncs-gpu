"""cpu_plugins.optimization.randomx_optimizer

Tối ưu hóa RandomX Algorithm cho Intel Xeon E5-2690 v4.
Tối ưu hóa L3 Cache, Instruction Set và Performance cho XMR Mining.
"""

import os
import psutil
import logging
import platform
from typing import Dict, List, Any, Optional


class CPUFeatureDetector:
    """
    Phát hiện CPU features và capabilities cho optimization.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Khởi tạo detector."""
        self.logger = logger or logging.getLogger(__name__)
        self.cpu_info = self._detect_cpu_info()
        self.cache_info = self._detect_cache_topology()
        
        # Sửa lỗi brand key
        cpu_model = self.cpu_info.get('brand', 'Intel Xeon E5-2690 v4')
        self.logger.info(f"CPU Detection: {cpu_model} - {self.cpu_info['cores']} cores")
    
    def _detect_cpu_info(self) -> Dict[str, Any]:
        """Phát hiện thông tin CPU."""
        features = self._get_cpu_flags()
        
        # Phát hiện tên model CPU
        cpu_model = "Intel Xeon E5-2690 v4"
        try:
            if platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            cpu_model = line.split(':', 1)[1].strip()
                            break
        except Exception:
            pass
        
        return {
            'brand': cpu_model,
            'cores': psutil.cpu_count(logical=False) or 12,
            'threads': psutil.cpu_count(logical=True) or 12,
            'features': features
        }
    
    def _get_cpu_flags(self) -> Dict[str, bool]:
        """Lấy các flags của CPU."""
        features = {
            'avx': False,
            'avx2': False, 
            'avx512': False,
            'aes': False,
            'fma': False,
            'sse4_1': False,
            'sse4_2': False
        }
        
        try:
            if platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r') as f:
                    content = f.read()
                    if 'avx2' in content:
                        features['avx2'] = True
                        features['avx'] = True
                    elif 'avx' in content:
                        features['avx'] = True
                    
                    if 'aes' in content:
                        features['aes'] = True
                    if 'fma' in content:
                        features['fma'] = True
                    if 'sse4_1' in content:
                        features['sse4_1'] = True
                    if 'sse4_2' in content:
                        features['sse4_2'] = True
        except Exception:
            # Mặc định cho Xeon E5-2690 v4
            features.update({
                'avx2': True,
                'avx': True, 
                'aes': True,
                'fma': True,
                'sse4_1': True,
                'sse4_2': True
            })
            
        return features
    
    def _detect_cache_topology(self) -> Dict[str, Any]:
        """Phát hiện cấu trúc cache."""
        cache_info = {'l3_size': 35 * 1024 * 1024}  # 35MB cho Xeon E5-2690 v4
        
        try:
            if platform.system() == 'Linux':
                l3_path = '/sys/devices/system/cpu/cpu0/cache/index3/size'
                if os.path.exists(l3_path):
                    with open(l3_path, 'r') as f:
                        size_str = f.read().strip()
                        if 'K' in size_str:
                            cache_info['l3_size'] = int(size_str.replace('K', '')) * 1024
        except Exception:
            pass
            
        self.logger.info(f"Cache detected: L3={cache_info['l3_size'] // 1024 // 1024}MB")
        return cache_info


class RandomXCacheOptimizer:
    """
    Tối ưu hóa L3 Cache cho RandomX Algorithm.
    """
    
    def __init__(self, cpu_detector: CPUFeatureDetector, logger: Optional[logging.Logger] = None):
        """Khởi tạo optimizer."""
        self.logger = logger or logging.getLogger(__name__)
        self.cpu_detector = cpu_detector
        self.l3_cache_size = cpu_detector.cache_info['l3_size']
        self.physical_cores = cpu_detector.cpu_info['cores']
        
        self.logger.info(f"RandomX Cache Optimizer: L3={self.l3_cache_size//1024//1024}MB, Cores={self.physical_cores}")
    
    def calculate_optimal_threads(self) -> Dict[str, int]:
        """Tính toán số luồng tối ưu cho các profile khác nhau."""
        # Cho Xeon E5-2690 v4: 12 cores, optimal threads
        core_based = max(1, self.physical_cores - 2)  # Để lại 2 cores cho hệ thống
        stealth_threads = max(1, self.physical_cores // 2)
        
        return {
            'maximum_performance': min(core_based, 10),
            'balanced': min(core_based, 8), 
            'stealth': stealth_threads,
            'recommended': 8
        }
    
    def generate_cache_friendly_affinity(self, thread_count: int) -> List[List[int]]:
        """Tạo cấu hình affinity thân thiện với cache."""
        available_cores = list(range(self.physical_cores))
        
        # Phân phối đơn giản
        result = []
        for i in range(thread_count):
            core_id = available_cores[i % len(available_cores)]
            result.append([core_id])
        
        self.logger.info(f"Cache-friendly affinity groups: {result}")
        return result


class InstructionSetOptimizer:
    """
    Tối ưu hóa Instruction Set cho RandomX trên Xeon E5-2690 v4.
    """
    
    def __init__(self, cpu_detector: CPUFeatureDetector, logger: Optional[logging.Logger] = None):
        """Khởi tạo optimizer."""
        self.logger = logger or logging.getLogger(__name__)
        self.cpu_features = cpu_detector.cpu_info['features']
        self.optimal_instruction_set = self._select_optimal_isa()
        
        self.logger.info(f"Optimal ISA: {self.optimal_instruction_set}")
    
    def _select_optimal_isa(self) -> str:
        """Chọn instruction set tối ưu."""
        if self.cpu_features.get('avx2') and self.cpu_features.get('fma'):
            return 'avx2_fma'
        elif self.cpu_features.get('avx2'):
            return 'avx2'
        elif self.cpu_features.get('avx'):
            return 'avx'
        else:
            return 'sse4'
    
    def get_compiler_flags(self) -> Dict[str, str]:
        """Lấy các compiler flags tối ưu."""
        flag_mapping = {
            'avx2_fma': '-march=broadwell -mavx2 -mfma -maes',
            'avx2': '-mavx2 -maes',
            'avx': '-mavx -maes', 
            'sse4': '-msse4.1 -msse4.2'
        }
        
        base_flags = flag_mapping.get(self.optimal_instruction_set, '-O2')
        
        return {
            'base_flags': base_flags,
            'optimization_flags': '-O3 -ffast-math',
            'combined_flags': f"{base_flags} -O3 -ffast-math"
        }
    
    def estimate_performance_gain(self) -> float:
        """Ước tính mức tăng hiệu năng."""
        gains = {
            'avx2_fma': 1.15,
            'avx2': 1.12,
            'avx': 1.08,
            'sse4': 1.05
        }
        return gains.get(self.optimal_instruction_set, 1.0)


class XeonE5OptimizedConfig:
    """
    Configuration tổng hợp tối ưu cho Xeon E5-2690 v4.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Khởi tạo cấu hình."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Khởi tạo các thành phần
        self.cpu_detector = CPUFeatureDetector(logger)
        self.cache_optimizer = RandomXCacheOptimizer(self.cpu_detector, logger)
        self.isa_optimizer = InstructionSetOptimizer(self.cpu_detector, logger)
        
        self.logger.info("Xeon E5-2690 v4 optimization framework initialized")
    
    def generate_mining_config(self, performance_profile: str = 'balanced', use_optimized_chain: bool = True) -> Dict[str, Any]:
        """
        Tạo cấu hình mining tối ưu với enhanced stealth profiles.
        
        Args:
            performance_profile: 'maximum', 'balanced', 'stealth', 'ninja', 'ghost', 'optimized'
            use_optimized_chain: Enable new OptimizedCalculationChain for 800% CPU utilization
        
        Returns:
            Cấu hình tối ưu cho RandomX mining
        """
        thread_options = self.cache_optimizer.calculate_optimal_threads()
        
        # NEW: Optimized profile for maximum CPU utilization
        if performance_profile == 'optimized' and use_optimized_chain:
            return self._generate_optimized_chain_config(thread_options)
        
        # Ánh xạ profile nâng cao với stealth considerations
        profile_mapping = {
            'maximum': {
                'threads': thread_options.get('maximum_performance', 10),
                'cpu_limit': 100 if use_optimized_chain else 90,  # Allow 100% if using optimized chain
                'priority': 0,
                'stealth_level': 'none',
                'optimized_chain_enabled': use_optimized_chain
            },
            'balanced': {
                'threads': thread_options.get('balanced', 8),
                'cpu_limit': 100 if use_optimized_chain else 70,  # Enhanced for optimized chain
                'priority': 5,
                'stealth_level': 'low',
                'optimized_chain_enabled': use_optimized_chain
            },
            'stealth': {
                'threads': thread_options.get('stealth', 6),
                'cpu_limit': 50,
                'priority': 10,
                'stealth_level': 'medium'
            },
            'ninja': {
                'threads': max(1, thread_options.get('stealth', 6) // 2),
                'cpu_limit': 30,
                'priority': 15,
                'stealth_level': 'high'
            },
            'ghost': {
                'threads': 1,
                'cpu_limit': 15,
                'priority': 19,
                'stealth_level': 'maximum'
            }
        }
        
        # Lấy cấu hình cho profile đã chọn hoặc fallback về balanced
        profile_config = profile_mapping.get(performance_profile, profile_mapping['balanced'])
        
        # Tính toán affinity tối ưu
        thread_count = profile_config['threads']
        affinity_groups = self.cache_optimizer.generate_cache_friendly_affinity(thread_count)
        
        # Tính toán hiệu suất dự kiến
        base_hashrate = self._estimate_base_hashrate()
        isa_gain = self.isa_optimizer.estimate_performance_gain()
        stealth_penalty = self._get_stealth_penalty(profile_config['stealth_level'])
        
        estimated_hashrate = base_hashrate * isa_gain * stealth_penalty * thread_count
        efficiency_rating = self._calculate_efficiency_rating(profile_config)
        
        # Tạo cấu hình cuối cùng
        config = {
            'profile': performance_profile,
            'threads': thread_count,
            'affinity': affinity_groups,
            'cpu_limit': profile_config['cpu_limit'],
            'priority': profile_config['priority'],
            'stealth_level': profile_config['stealth_level'],
            'estimated_hashrate': estimated_hashrate,
            'efficiency_rating': efficiency_rating,
            'instruction_set': self.isa_optimizer.optimal_instruction_set,
            'compiler_flags': self.isa_optimizer.get_compiler_flags()['combined_flags']
        }
        
        self.logger.info(f"Generated RandomX config for profile '{performance_profile}': {thread_count} threads, {estimated_hashrate:.2f} H/s")
        return config
    
    def _estimate_base_hashrate(self) -> float:
        """Ước tính hashrate cơ bản cho một thread."""
        # Giá trị tham khảo cho Xeon E5-2690 v4
        base_hashrate = 100.0  # H/s per thread
        
        # Điều chỉnh dựa trên cache size
        l3_per_core = self.cpu_detector.cache_info['l3_size'] / self.cpu_detector.cpu_info['cores']
        cache_factor = min(1.2, max(0.8, l3_per_core / (2.5 * 1024 * 1024)))
        
        return base_hashrate * cache_factor
    
    def _get_stealth_penalty(self, stealth_level: str) -> float:
        """Lấy hệ số giảm hiệu năng do stealth."""
        penalties = {
            'none': 1.0,
            'low': 0.95,
            'medium': 0.85,
            'high': 0.7,
            'maximum': 0.5
        }
        return penalties.get(stealth_level, 0.85)
    
    def _calculate_efficiency_rating(self, profile_config: Dict[str, Any]) -> str:
        """Tính toán xếp hạng hiệu quả của cấu hình."""
        stealth_level = profile_config['stealth_level']
        
        if stealth_level == 'none':
            return 'Performance'
        elif stealth_level == 'low':
            return 'Balanced'
        elif stealth_level == 'medium':
            return 'Efficient'
        elif stealth_level == 'high':
            return 'Stealth'
        else:
            return 'Ultra Stealth'
    
    def get_stealth_optimized_config(self) -> Dict[str, Any]:
        """Lấy cấu hình tối ưu cho stealth mining."""
        return self.generate_mining_config('stealth')
    
    def _generate_optimized_chain_config(self, thread_options: Dict[str, int]) -> Dict[str, Any]:
        """
        Generate configuration cho OptimizedCalculationChain.
        Target: 800% CPU utilization across 8 cores với multi-process architecture.
        """
        # Import optimized components
        try:
            from .optimized_calculation_chain import create_optimized_mining_chain
            from .workload_distributor import create_balanced_distributor, TaskProfile
            from .low_overhead_sync import create_high_performance_sync
        except ImportError as e:
            self.logger.error(f"Failed to import optimized chain components: {e}")
            # Fallback to balanced profile
            return self.generate_mining_config('balanced', use_optimized_chain=False)
        
        # Core configuration for optimized chain
        cores = self.cpu_detector.cpu_info['cores']
        threads = min(cores, thread_options.get('balanced', 8))
        
        # Calculate estimated performance với optimized architecture
        base_hashrate = self._estimate_base_hashrate()
        isa_gain = self.isa_optimizer.estimate_performance_gain()
        
        # Optimized chain có performance gain 6.67x (từ 1.2 cores → 8.0 cores)
        optimization_multiplier = 6.67
        estimated_hashrate = base_hashrate * isa_gain * optimization_multiplier * cores
        
        # Create optimized configuration
        config = {
            'profile': 'optimized',
            'architecture': 'multi_process_optimized',
            'cores': cores,
            'threads': threads,
            'cpu_limit': 100,  # Allow 100% per core
            'target_cpu_utilization': 800,  # 8 cores × 100% - restored to original target
            'priority': -5,  # High priority for maximum performance
            'stealth_level': 'none',
            'optimized_chain_enabled': True,
            
            # Performance characteristics
            'estimated_hashrate': estimated_hashrate,
            'efficiency_rating': 'Maximum Performance',
            'optimization_multiplier': optimization_multiplier,
            'performance_target': '800% CPU utilization (8 cores max)',
            
            # Technical specifications
            'instruction_set': self.isa_optimizer.optimal_instruction_set,
            'compiler_flags': self.isa_optimizer.get_compiler_flags()['combined_flags'],
            'cache_optimization': True,
            'thermal_management': True,
            
            # Component configurations
            'calculation_chain': {
                'type': 'OptimizedCalculationChain',
                'cores': cores,
                'worker_processes': cores,
                'queue_size': cores * 12,  # Increased to 144 for 12 cores
                'target_utilization_per_core': 100
            },
            
            'workload_distributor': {
                'type': 'AdaptiveLoadBalancer',
                'strategy': 'performance_weighted',
                'cores': cores,
                'thermal_aware': True,
                'cache_aware': True
            },
            
            'synchronization': {
                'type': 'LowOverheadSynchronization',
                'cores': cores,
                'target_overhead': 5,  # <5% overhead
                'shared_memory_size': 8192,
                'adaptive_barriers': True
            },
            
            # Performance monitoring
            'monitoring': {
                'enabled': True,
                'interval': 1.0,
                'metrics': ['cpu_utilization', 'hashrate', 'thermal_status', 'memory_usage'],
                'adaptive_tuning': True
            },
            
            # Integration points
            'integration': {
                'replace_subprocess': True,
                'start_mining_integration': True,
                'throttling_compatible': True,
                'stealth_fallback': 'balanced'
            }
        }
        
        self.logger.info(f"Generated optimized chain config: {cores} cores, {estimated_hashrate:.2f} H/s target")
        return config 