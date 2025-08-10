    def _emergency_scaling(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scale down parameters for emergency temperature control
        
        :param params: Original parameters
        :return: Scaled parameters
        """
        self.logger.warning(f"🚨 [OHC._emergency_scaling] Entry - emergency scaling activated!")
        scaled = params.copy()
        
        # Reduce power by 30%
        if 'power_limit' in scaled:
            original_power = scaled['power_limit']
            scaled['power_limit'] = int(scaled['power_limit'] * 0.7)
            self.logger.info(f"⬇️ [OHC._emergency_scaling] Reducing power: {original_power}W → {scaled['power_limit']}W (-30%)")
        
        # Reduce clocks by 20%
        if 'sm_clock' in scaled:
            original_clock = scaled['sm_clock']
            scaled['sm_clock'] = int(scaled['sm_clock'] * 0.8)
            self.logger.info(f"⬇️ [OHC._emergency_scaling] Reducing SM clock: {original_clock}MHz → {scaled['sm_clock']}MHz (-20%)")
        
        # Add aggressive fan control
        scaled['fan_increase'] = 30.0  # 30% fan increase
        self.logger.info(f"💨 [OHC._emergency_scaling] Setting aggressive fan increase: 30%")
        
        self.logger.debug(f"✅ [OHC._emergency_scaling] Exit - scaled params: {list(scaled.keys())}")
        return scaled
    
    def _apply_nvml_controls(self, pid: int, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Apply NVML-based controls (power, clocks)
        """
        self.logger.debug(f"⚡ [OHC._apply_nvml_controls] Entry - PID: {pid}, GPU: {gpu_index}, params: {list(params.keys())}")
        success = True
        
        try:
            # Power limit
            if 'power_limit' in params:
                power_w = params['power_limit']
                self.logger.debug(f"🔌 [OHC._apply_nvml_controls] Setting power limit to {power_w}W...")
                
                # Get current power for smooth transition
                current_power = self._get_current_power(gpu_index)
                target_power = params['power_limit']
                
                # Smooth transition if large change
                if abs(target_power - current_power) > 20:
                    self.logger.debug(f"📈 [OHC._apply_nvml_controls] Large power change detected ({current_power}W → {target_power}W), using step-wise adjustment...")
                    steps = 3
                    for i in range(steps):
                        intermediate = current_power + (target_power - current_power) * (i+1) / steps
                        self.logger.debug(f"  Step {i+1}/{steps}: Setting to {intermediate:.1f}W")
                        if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, int(intermediate)):
                            self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed at step {i+1}")
                            success = False
                            break
                        time.sleep(0.1)
                else:
                    if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, power_w):
                        self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set power limit {power_w}W for GPU {gpu_index}")
                        success = False
                    else:
                        self.logger.info(f"✅ [OHC._apply_nvml_controls] Power limit set to {power_w}W for GPU {gpu_index}")
            
            # Clock speeds
            if 'sm_clock' in params and 'mem_clock' in params:
                sm_mhz = params['sm_clock']
                mem_mhz = params['mem_clock']
                self.logger.debug(f"⏱️ [OHC._apply_nvml_controls] Setting clocks - SM: {sm_mhz}MHz, Mem: {mem_mhz}MHz...")
                if not self.gpu_manager.set_gpu_clocks(pid, gpu_index, sm_mhz, mem_mhz):
                    self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set clocks (SM: {sm_mhz}MHz, Mem: {mem_mhz}MHz) for GPU {gpu_index}")
                    success = False
                else:
                    self.logger.info(f"✅ [OHC._apply_nvml_controls] Clocks set - SM: {sm_mhz}MHz, Mem: {mem_mhz}MHz for GPU {gpu_index}")
            
            # Temperature control
            if 'temperature' in params:
                temp_target = params['temperature']
                fan_increase = (temp_target - 60) * 2  # Simple linear scaling
                self.logger.debug(f"🌡️ [OHC._apply_nvml_controls] Setting temp target: {temp_target}°C, fan increase: {fan_increase}%...")
                if not self.gpu_manager.limit_temperature(pid, gpu_index, temp_target, fan_increase):
                    self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set temperature limit {temp_target}°C for GPU {gpu_index}")
                    success = False
                else:
                    self.logger.info(f"✅ [OHC._apply_nvml_controls] Temperature target set to {temp_target}°C for GPU {gpu_index}")
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._apply_nvml_controls] Exception: {e}", exc_info=True)
            success = False
        
        self.logger.debug(f"{'✅' if success else '❌'} [OHC._apply_nvml_controls] Exit - success: {success}")
        return success

    def _get_current_power(self, gpu_index: int) -> float:
        """
        Get current GPU power usage
        
        :return: Power in Watts
        """
        self.logger.debug(f"🔍 [OHC._get_current_power] Getting power for GPU {gpu_index}")
        
        try:
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            power_mw = pynvml.nvmlDeviceGetPowerUsage(gpu_handle)
            power_w = power_mw / 1000.0  # Convert to Watts
            self.logger.debug(f"✅ [OHC._get_current_power] GPU {gpu_index} power: {power_w:.1f}W")
            return power_w
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._get_current_power] Cannot read power for GPU {gpu_index}: {e}, using baseline {self.baseline_power}W")
            return self.baseline_power  # Return baseline if can't read

    def _apply_compute_simulation(self, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Apply compute load simulation
        """
        self.logger.debug(f"🔢 [OHC._apply_compute_simulation] Entry - GPU: {gpu_index}, params: {list(params.keys())}")
        
        try:
            pattern = params.get('compute_pattern', 'sine')
            duration = params.get('compute_duration', 10)
            intensity = params.get('compute_intensity', 0.5)
            self.logger.info(f"🎯 [OHC._apply_compute_simulation] Starting {pattern} pattern for {duration}s at {intensity*100}% intensity on GPU {gpu_index}")
            
            # Calculate duty cycle based on target power
            target_power = params.get('power_limit', self.baseline_power)
            duty_cycle = target_power / self.baseline_power
            duty_cycle = max(0.5, min(1.0, duty_cycle))
            self.logger.debug(f"📊 [OHC._apply_compute_simulation] Calculated duty cycle: {duty_cycle:.2f} (target power: {target_power}W, baseline: {self.baseline_power}W)")
            
            # Launch compute kernel với duty cycle
            compute_cmd = f"""
python3 -c "
import torch
import time
import sys

try:
    # Allocate tensors
    a = torch.randn(2000, 2000, device='cuda')
    b = torch.randn(2000, 2000, device='cuda')
    
    # Run với duty cycle
    work_time = {duty_cycle * 0.1}  # 100ms window
    sleep_time = {(1 - duty_cycle) * 0.1}
    
    for _ in range(10):
        start = time.time()
        while time.time() - start < work_time:
            c = torch.matmul(a, b)
            torch.cuda.synchronize()
        time.sleep(sleep_time)
except Exception as e:
    print(f'Compute simulation error: {{e}}', file=sys.stderr)
" &
            """
            
            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(gpu_index)
            
            self.logger.debug(f"🚀 [OHC._apply_compute_simulation] Launching compute subprocess with CUDA_VISIBLE_DEVICES={gpu_index}")
            
            proc = subprocess.Popen(
                compute_cmd, 
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            self.active_subprocesses.append(proc)
            self.logger.info(f"✅ [OHC._apply_compute_simulation] Started compute subprocess PID: {proc.pid} on GPU {gpu_index} (duty cycle: {duty_cycle:.2f})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._apply_compute_simulation] Failed to start compute simulation: {e}", exc_info=True)
            return False
