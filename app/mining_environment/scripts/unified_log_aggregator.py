#!/usr/bin/env python3
"""
✅ UNIFIED LOG AGGREGATOR (bộ tổng hợp log đồng nhất)
Creates unified.log từ all specialized log files trong unified logging system.
Provides single view của toàn bộ system activity cho easier debugging.
"""

import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import re

class UnifiedLogAggregator:
    """
    ✅ LOG AGGREGATION: Tạo unified.log từ all specialized logs
    Merges chronologically và maintains source traceability
    """
    
    def __init__(self, log_dir: str = "/app/mining_environment/logs"):
        self.log_dir = Path(log_dir)
        self.unified_log_path = self.log_dir / "unified.log"
        self.last_positions: Dict[str, int] = {}
        self.running = False
        self.thread = None
        
        # ✅ PATTERN: Regex để extract timestamp từ log lines
        self.timestamp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
        
    def start_aggregation(self, interval: float = 5.0):
        """
        🚀 START: Bắt đầu real-time log aggregation
        
        Args:
            interval: Polling interval in seconds
        """
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(
            target=self._aggregation_loop,
            args=(interval,),
            daemon=True,
            name="UnifiedLogAggregator"
        )
        self.thread.start()
        print(f"✅ [UnifiedLogAggregator] Started - unified.log: {self.unified_log_path}")
        
    def stop_aggregation(self):
        """🛑 STOP: Dừng log aggregation"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        print("🛑 [UnifiedLogAggregator] Stopped")
        
    def _aggregation_loop(self, interval: float):
        """
        🔄 MAIN LOOP: Continuous log aggregation
        """
        while self.running:
            try:
                self._aggregate_logs()
                time.sleep(interval)
            except Exception as e:
                print(f"❌ [UnifiedLogAggregator] Error: {e}")
                time.sleep(interval * 2)  # Back off on error
                
    def _aggregate_logs(self):
        """
        📊 AGGREGATE: Collect new log entries từ all log files
        """
        if not self.log_dir.exists():
            return
            
        # ✅ DISCOVER: Find all log files
        log_files = list(self.log_dir.glob("*.log"))
        if not log_files:
            return
            
        # ✅ COLLECT: Gather new entries từ each log file
        new_entries: List[Tuple[datetime, str, str]] = []
        
        for log_file in log_files:
            if log_file.name == "unified.log":
                continue  # Skip own file
                
            try:
                entries = self._read_new_entries(log_file)
                new_entries.extend(entries)
            except Exception as e:
                print(f"⚠️ [UnifiedLogAggregator] Error reading {log_file.name}: {e}")
                
        # ✅ SORT: Sort by timestamp
        new_entries.sort(key=lambda x: x[0])
        
        # ✅ WRITE: Append to unified.log
        if new_entries:
            self._write_unified_entries(new_entries)
            
    def _read_new_entries(self, log_file: Path) -> List[Tuple[datetime, str, str]]:
        """
        📖 READ: Extract new entries từ specific log file
        
        Returns:
            List of (timestamp, source_file, log_line) tuples
        """
        entries = []
        
        if not log_file.exists():
            return entries
            
        # ✅ TRACK: Get last read position
        last_pos = self.last_positions.get(str(log_file), 0)
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_pos)
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # ✅ EXTRACT: Parse timestamp
                    timestamp = self._extract_timestamp(line)
                    if timestamp:
                        entries.append((timestamp, log_file.name, line))
                        
                # ✅ UPDATE: Save new position
                self.last_positions[str(log_file)] = f.tell()
                
        except Exception as e:
            print(f"⚠️ [UnifiedLogAggregator] Error reading {log_file}: {e}")
            
        return entries
        
    def _extract_timestamp(self, line: str) -> datetime:
        """
        🕐 PARSE: Extract timestamp từ log line
        
        Returns:
            datetime object hoặc None if not found
        """
        match = self.timestamp_pattern.search(line)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return datetime.now()  # Fallback to current time
        
    def _write_unified_entries(self, entries: List[Tuple[datetime, str, str]]):
        """
        ✍️ WRITE: Append entries to unified.log
        
        Args:
            entries: List of (timestamp, source_file, log_line) tuples
        """
        try:
            with open(self.unified_log_path, 'a', encoding='utf-8') as f:
                for timestamp, source_file, log_line in entries:
                    # ✅ FORMAT: Add source file prefix
                    unified_line = f"[{source_file}] {log_line}\n"
                    f.write(unified_line)
                    
        except Exception as e:
            print(f"❌ [UnifiedLogAggregator] Error writing unified.log: {e}")

# ✅ SINGLETON: Global aggregator instance
_aggregator = None
_aggregator_lock = threading.Lock()

def get_unified_aggregator() -> UnifiedLogAggregator:
    """
    🏭 FACTORY: Get singleton unified log aggregator
    
    Returns:
        UnifiedLogAggregator instance
    """
    global _aggregator
    
    with _aggregator_lock:
        if _aggregator is None:
            _aggregator = UnifiedLogAggregator()
        return _aggregator

def start_unified_logging():
    """
    🚀 CONVENIENCE: Start unified log aggregation
    """
    aggregator = get_unified_aggregator()
    aggregator.start_aggregation()
    
def stop_unified_logging():
    """
    🛑 CONVENIENCE: Stop unified log aggregation
    """
    global _aggregator
    if _aggregator:
        _aggregator.stop_aggregation()

if __name__ == "__main__":
    # ✅ STANDALONE: Run as standalone aggregator
    print("🚀 [UnifiedLogAggregator] Starting standalone mode...")
    
    aggregator = UnifiedLogAggregator()
    
    try:
        aggregator.start_aggregation(interval=2.0)
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 [UnifiedLogAggregator] Shutting down...")
        aggregator.stop_aggregation()