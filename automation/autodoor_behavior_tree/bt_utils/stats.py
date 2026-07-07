import time
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from bt_utils.log_manager import LogManager


@dataclass
class NodeStatistics:
    node_id: str
    node_type: str
    node_name: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    running_count: int = 0
    aborted_count: int = 0
    total_time_ms: float = 0.0
    max_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    _last_status: str = ""
    
    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.success_count / self.total_executions
    
    @property
    def avg_time_ms(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_time_ms / self.total_executions
    
    def record(self, status: str, duration_ms: float):
        self.total_executions += 1
        self.total_time_ms += duration_ms
        self.max_time_ms = max(self.max_time_ms, duration_ms)
        self.min_time_ms = min(self.min_time_ms, duration_ms) if self.min_time_ms != float('inf') else duration_ms
        self._last_status = status
        
        if status == "success":
            self.success_count += 1
        elif status == "failure":
            self.failure_count += 1
        elif status == "running":
            self.running_count += 1
        elif status == "aborted":
            self.aborted_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "node_name": self.node_name,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "running_count": self.running_count,
            "aborted_count": self.aborted_count,
            "success_rate": round(self.success_rate * 100, 2),
            "total_time_ms": round(self.total_time_ms, 4),
            "avg_time_ms": round(self.avg_time_ms, 4),
            "max_time_ms": round(self.max_time_ms, 4),
            "min_time_ms": round(self.min_time_ms, 4) if self.min_time_ms != float('inf') else 0,
            "last_status": self._last_status
        }


class StatsCollector:
    def __init__(self):
        self._stats: Dict[str, NodeStatistics] = {}
        self._start_time: float = 0
        self._end_time: float = 0
        self._tick_count: int = 0
        self._enabled: bool = True
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def start_session(self):
        self._start_time = time.time()
        self._tick_count = 0
        self._stats.clear()
    
    def end_session(self):
        self._end_time = time.time()
    
    def record_tick(self):
        self._tick_count += 1
    
    def record_node(self, node_id: str, node_type: str, node_name: str,
                    status: str, duration_ms: float):
        if not self._enabled:
            return
        
        if node_id not in self._stats:
            self._stats[node_id] = NodeStatistics(
                node_id=node_id,
                node_type=node_type,
                node_name=node_name
            )
        
        self._stats[node_id].record(status, duration_ms)
    
    def get_node_stats(self, node_id: str) -> Optional[NodeStatistics]:
        return self._stats.get(node_id)
    
    def get_all_stats(self) -> Dict[str, NodeStatistics]:
        return self._stats
    
    def get_session_duration_ms(self) -> float:
        if self._end_time > 0:
            return (self._end_time - self._start_time) * 1000
        return (time.time() - self._start_time) * 1000
    
    def get_report(self) -> Dict[str, Any]:
        total_executions = sum(s.total_executions for s in self._stats.values())
        total_success = sum(s.success_count for s in self._stats.values())
        total_failure = sum(s.failure_count for s in self._stats.values())
        
        sorted_by_time = sorted(
            self._stats.values(),
            key=lambda s: s.total_time_ms,
            reverse=True
        )
        
        sorted_by_count = sorted(
            self._stats.values(),
            key=lambda s: s.total_executions,
            reverse=True
        )
        
        return {
            "session": {
                "start_time": datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else "",
                "end_time": datetime.fromtimestamp(self._end_time).isoformat() if self._end_time else "",
                "duration_ms": round(self.get_session_duration_ms(), 2),
                "tick_count": self._tick_count,
                "total_node_executions": total_executions,
                "total_success": total_success,
                "total_failure": total_failure,
            },
            "summary": {
                "node_count": len(self._stats),
                "average_executions_per_node": round(total_executions / len(self._stats), 2) if self._stats else 0,
                "success_rate": round(total_success / total_executions * 100, 2) if total_executions > 0 else 0,
            },
            "top_by_time": [s.to_dict() for s in sorted_by_time[:10]],
            "top_by_count": [s.to_dict() for s in sorted_by_count[:10]],
            "nodes": {nid: s.to_dict() for nid, s in self._stats.items()}
        }
    
    def export_to_file(self, filepath: str) -> bool:
        try:
            report = self.get_report()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            LogManager.debug_print(f"导出统计报告失败: {e}")
            return False
    
    def reset(self):
        self._stats.clear()
        self._start_time = 0
        self._end_time = 0
        self._tick_count = 0


class NoOpStatsCollector:
    def __init__(self):
        self._enabled = False
    
    def is_enabled(self) -> bool:
        return False
    
    def start_session(self):
        pass
    
    def end_session(self):
        pass
    
    def record_tick(self):
        pass
    
    def record_node(self, node_id: str, node_type: str, node_name: str,
                    status: str, duration_ms: float):
        pass
    
    def get_node_stats(self, node_id: str) -> Optional[NodeStatistics]:
        return None
    
    def get_all_stats(self) -> Dict[str, NodeStatistics]:
        return {}
    
    def get_session_duration_ms(self) -> float:
        return 0.0
    
    def get_report(self) -> Dict[str, Any]:
        return {}
    
    def export_to_file(self, filepath: str) -> bool:
        return False
    
    def reset(self):
        pass


def is_debug_mode() -> bool:
    try:
        import sys
        if not getattr(sys, 'frozen', False):
            return True
        
        from bt_utils.version_checker import load_build_info
        build_info = load_build_info()
        return build_info.get('debug', {}).get('enable_debug_mode', False)
    except Exception:
        return True


_stats_collector: Optional[StatsCollector] = None


def get_stats_collector() -> StatsCollector:
    global _stats_collector
    if _stats_collector is None:
        if is_debug_mode():
            _stats_collector = StatsCollector()
        else:
            _stats_collector = NoOpStatsCollector()
    return _stats_collector


def reset_stats_collector():
    global _stats_collector
    _stats_collector = None
