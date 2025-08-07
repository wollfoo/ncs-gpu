#!/usr/bin/env python3
"""
NVML IPC Proxy Daemon - Chặn và sửa phản hồi NVML
Chiếm socket NVML, forward request và modify response
"""

import os
import socket
import struct
import threading
import logging
import json
import time
import signal
import sys
from pathlib import Path

# Import logger from module_loggers
try:
    from ....scripts.module_loggers import get_proxy_daemon_logger
    logger = get_proxy_daemon_logger()
except ImportError:
    # Fallback logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('NVMLProxy')

class NVMLProxy:
    def __init__(self):
        self.original_socket = "/var/run/nvidia-persistenced/socket"
        self.proxy_socket = "/var/run/nvidia-persistenced/socket.original"
        self.backup_socket = "/var/run/nvidia-persistenced/socket.backup"
        
        # Fake values từ environment
        self.fake_utilization = int(os.getenv('NVML_FAKE_UTIL', '0'))
        self.fake_temperature = int(os.getenv('NVML_FAKE_TEMP', '50'))
        self.fake_memory_used = int(os.getenv('NVML_FAKE_MEM_MB', '100'))
        self.add_noise = os.getenv('NVML_ADD_NOISE', '0') == '1'
        
        self.running = False
        self.proxy_sock = None
        
        logger.info(f"NVML Proxy initialized - Util: {self.fake_utilization}%, Temp: {self.fake_temperature}°C, Mem: {self.fake_memory_used}MB")
        
    def _free_socket(self):
        """Giải phóng socket nếu bị process khác giữ (nvidia-persistenced)"""
        if not os.path.exists(self.original_socket):
            logger.debug("Socket chưa tồn tại, bỏ qua _free_socket()")
            return
        # Không chạy fuser/pkill để tránh dừng service nvidia-persistenced
        logger.debug("Giữ nguyên process nvidia-persistenced; bỏ giải phóng FD")

    def start(self):
        """Khởi động proxy daemon"""
        try:
            # Kiểm tra socket gốc
            if not os.path.exists(self.original_socket):
                logger.error(f"Original socket not found: {self.original_socket}")
                return False
                
            # Nếu socket gốc tồn tại, cố gắng rename sang socket.original
            if os.path.exists(self.original_socket):
                self._free_socket()
                retry = 0
                while retry < 3:
                    try:
                        os.rename(self.original_socket, self.proxy_socket)
                        break
                    except OSError as e:
                        if e.errno == 16:  # EBUSY
                            self._free_socket()
                            retry += 1
                            time.sleep(0.5 * retry)
                            continue
                        raise
                else:
                    logger.error("Failed to move socket after retries")
                    return False
            else:
                # Không có socket gốc, tiếp tục tạo socket mới
                logger.warning(f"Original socket not found, sẽ tạo socket mới tại {self.original_socket}")
                
            # Tạo proxy socket
            self.proxy_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            
            # Xóa socket cũ nếu tồn tại
            if os.path.exists(self.original_socket):
                os.unlink(self.original_socket)
                
            self.proxy_sock.bind(self.original_socket)
            self.proxy_sock.listen(5)
            
            # Set permissions giống socket gốc
            os.chmod(self.original_socket, 0o666)
            
            self.running = True
            logger.info(f"NVML Proxy listening on {self.original_socket}")
            
            # Accept connections
            while self.running:
                try:
                    client, _ = self.proxy_sock.accept()
                    threading.Thread(
                        target=self.handle_client, 
                        args=(client,),
                        daemon=True
                    ).start()
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            return False
            
        return True
        
    def handle_client(self, client_sock):
        """Xử lý kết nối từ client"""
        nvml_sock = None
        try:
            # Kết nối tới NVML gốc
            nvml_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            nvml_sock.connect(self.proxy_socket)
            
            while True:
                # Nhận data từ client
                data = client_sock.recv(4096)
                if not data:
                    break
                    
                # Forward tới NVML
                nvml_sock.sendall(data)
                
                # Nhận response từ NVML
                response = b''
                while True:
                    chunk = nvml_sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    
                    # Check if we have complete response
                    if len(response) >= 4:
                        # Simple check - actual protocol is more complex
                        if b'\x00\x00\x00\x00' in response[-4:]:
                            break
                
                # Modify response
                modified_response = self.modify_response(response)
                
                # Send back to client
                client_sock.sendall(modified_response)
                
        except Exception as e:
            logger.debug(f"Client handler error: {e}")
        finally:
            if nvml_sock:
                nvml_sock.close()
            client_sock.close()
            
    def modify_response(self, data):
        """Sửa đổi response NVML"""
        try:
            # Thêm noise nếu được bật
            util = self.fake_utilization
            temp = self.fake_temperature
            mem = self.fake_memory_used
            
            if self.add_noise:
                import random
                util = max(0, min(100, util + random.randint(-5, 5)))
                temp = max(20, min(85, temp + random.randint(-3, 3)))
                mem = max(0, mem + random.randint(-50, 50))
            
            # Simple pattern matching - thực tế cần parse protocol chính xác
            # Tìm và thay thế các pattern số liệu GPU
            
            # Pattern cho utilization (giả định format)
            if b'gpu_util' in data or b'utilization' in data:
                logger.debug(f"Modifying utilization to {util}%")
                # Actual modification would be here
                
            # Pattern cho temperature
            if b'temperature' in data or b'temp_gpu' in data:
                logger.debug(f"Modifying temperature to {temp}°C")
                # Actual modification would be here
                
            # Pattern cho memory
            if b'memory_used' in data or b'mem_used' in data:
                logger.debug(f"Modifying memory to {mem}MB")
                # Actual modification would be here
                
        except Exception as e:
            logger.error(f"Error modifying response: {e}")
            
        return data
        
    def stop(self):
        """Dừng proxy và khôi phục socket gốc"""
        self.running = False
        
        if self.proxy_sock:
            self.proxy_sock.close()
            
        # Khôi phục socket gốc
        if os.path.exists(self.proxy_socket):
            if os.path.exists(self.original_socket):
                os.unlink(self.original_socket)
            os.rename(self.proxy_socket, self.original_socket)
            logger.info("Original socket restored")

def signal_handler(signum, frame):
    """Xử lý tín hiệu dừng"""
    logger.info(f"Received signal {signum}, shutting down...")
    if proxy:
        proxy.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start proxy
    proxy = NVMLProxy()
    
    if not proxy.start():
        logger.error("Failed to start NVML proxy")
        sys.exit(1) 