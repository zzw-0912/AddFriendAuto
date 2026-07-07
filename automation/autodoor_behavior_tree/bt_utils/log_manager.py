from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List
import threading
from bt_utils.singleton import singleton


class LogLevel(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ABORTED = "aborted"
    INFO = "info"
    TIMEOUT = "timeout"


@dataclass
class LogEntry:
    timestamp: datetime = field(default_factory=datetime.now)
    level: LogLevel = LogLevel.INFO
    node_type: str = ""
    node_name: str = ""
    message: str = ""
    tab_name: str = ""
    
    def format(self) -> str:
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        tab_prefix = f"[{self.tab_name}] " if self.tab_name else ""
        
        if self.level == LogLevel.SUCCESS:
            if self.message:
                return f"[{time_str}] {tab_prefix}✅ {self.node_type} \"{self.node_name}\" - 成功: {self.message}"
            return f"[{time_str}] {tab_prefix}✅ {self.node_type} \"{self.node_name}\" - 成功"
        elif self.level == LogLevel.FAILURE:
            return f"[{time_str}] {tab_prefix}❌ {self.node_type} \"{self.node_name}\" - 失败: {self.message}"
        elif self.level == LogLevel.TIMEOUT:
            return f"[{time_str}] {tab_prefix}⏱️ {self.node_type} \"{self.node_name}\" - 超时: {self.message}"
        elif self.level == LogLevel.ABORTED:
            return f"[{time_str}] {tab_prefix}⏸️ {self.node_type} \"{self.node_name}\" - 中止"
        else:
            return f"[{time_str}] {tab_prefix}ℹ️ {self.node_type} \"{self.node_name}\" - {self.message}"


def _is_console_output_enabled() -> bool:
    """检查是否启用终端输出
    
    Debug 环境（开发环境）: 启用终端输出
    Release 环境（打包后）: 禁用终端输出
    """
    try:
        import sys
        if not getattr(sys, 'frozen', False):
            return True
        
        from bt_utils.version_checker import load_build_info
        build_info = load_build_info()
        return build_info.get('debug', {}).get('enable_debug_mode', False)
    except Exception:
        return True


@singleton
class LogManager:
    """日志管理器
    
    使用单例模式，线程安全。
    
    日志分为两类：
    1. 前端日志：节点执行状态，始终显示在前端运行日志面板
    2. 终端日志：开发者调试信息，仅 Debug 环境输出到终端
    """
    
    _console_output_enabled: bool = None
    
    def __init__(self):
        self._buffer: List[LogEntry] = []
        self._buffer_lock = threading.Lock()
        self._stopped = False
        self._stopped_tabs: set = set()
        
        if LogManager._console_output_enabled is None:
            LogManager._console_output_enabled = _is_console_output_enabled()
    
    @classmethod
    def instance(cls) -> "LogManager":
        return cls()
    
    @classmethod
    def is_console_output_enabled(cls) -> bool:
        """检查是否启用终端输出"""
        if cls._console_output_enabled is None:
            cls._console_output_enabled = _is_console_output_enabled()
        return cls._console_output_enabled
    
    @classmethod
    def set_console_output(cls, enabled: bool) -> None:
        """设置终端输出开关
        
        Args:
            enabled: 是否启用终端输出
        """
        cls._console_output_enabled = enabled
    
    @classmethod
    def debug_print(cls, message: str) -> None:
        """终端调试输出（仅 Debug 环境）
        
        独立于前端日志，仅输出到终端，不添加到 buffer。
        用于开发者调试信息，如统计报告。
        
        Args:
            message: 调试消息
        """
        if not cls._console_output_enabled:
            if cls._console_output_enabled is None:
                cls._console_output_enabled = _is_console_output_enabled()
            if not cls._console_output_enabled:
                return
        
        try:
            print(message)
        except UnicodeEncodeError:
            try:
                import sys
                sys.stdout.buffer.write(message.encode('utf-8', errors='replace'))
                sys.stdout.buffer.write(b'\n')
                sys.stdout.buffer.flush()
            except Exception:
                pass
    
    def log(self, entry: LogEntry) -> None:
        """记录日志（仅前端显示，不输出到终端）
        
        Args:
            entry: 日志条目
        """
        if self._should_suppress_log(entry):
            return
        
        with self._buffer_lock:
            self._buffer.append(entry)
        
        try:
            from bt_utils.ui_dispatcher import UIUpdateDispatcher
            dispatcher = UIUpdateDispatcher()
            dispatcher.dispatch_log_flush()
        except ImportError:
            pass
    
    def _should_suppress_log(self, entry: LogEntry) -> bool:
        if entry.level not in (LogLevel.SUCCESS, LogLevel.FAILURE):
            return False
        if self._stopped:
            return True
        if entry.tab_name and entry.tab_name in self._stopped_tabs:
            return True
        return False
    
    def log_success(self, node_type: str, node_name: str, message: str = "", tab_name: str = "") -> None:
        """记录成功日志（前端显示）
        
        Args:
            node_type: 节点类型
            node_name: 节点名称
            message: 消息
            tab_name: Tab 名称
        """
        self.log(LogEntry(
            level=LogLevel.SUCCESS,
            node_type=node_type,
            node_name=node_name,
            message=message,
            tab_name=tab_name
        ))
    
    def log_failure(self, node_type: str, node_name: str, reason: str, tab_name: str = "") -> None:
        """记录失败日志（前端显示）
        
        Args:
            node_type: 节点类型
            node_name: 节点名称
            reason: 失败原因
            tab_name: Tab 名称
        """
        self.log(LogEntry(
            level=LogLevel.FAILURE,
            node_type=node_type,
            node_name=node_name,
            message=reason,
            tab_name=tab_name
        ))
    
    def log_aborted(self, node_type: str, node_name: str, tab_name: str = "") -> None:
        """记录中止日志（前端显示）
        
        Args:
            node_type: 节点类型
            node_name: 节点名称
            tab_name: Tab 名称
        """
        self.log(LogEntry(
            level=LogLevel.ABORTED,
            node_type=node_type,
            node_name=node_name,
            tab_name=tab_name
        ))
    
    def log_timeout(self, node_type: str, node_name: str, timeout_ms: int, tab_name: str = "") -> None:
        """记录超时日志（前端显示）
        
        Args:
            node_type: 节点类型
            node_name: 节点名称
            timeout_ms: 超时时间（毫秒）
            tab_name: Tab 名称
        """
        self.log(LogEntry(
            level=LogLevel.TIMEOUT,
            node_type=node_type,
            node_name=node_name,
            message=f"运行超时（{timeout_ms}ms）",
            tab_name=tab_name
        ))
    
    def log_info(self, node_type: str, node_name: str, message: str = "", tab_name: str = "") -> None:
        """记录信息日志（前端显示）
        
        Args:
            node_type: 节点类型
            node_name: 节点名称
            message: 消息
            tab_name: Tab 名称
        """
        self.log(LogEntry(
            level=LogLevel.INFO,
            node_type=node_type,
            node_name=node_name,
            message=message,
            tab_name=tab_name
        ))
    
    def set_stopped(self, stopped: bool, tab_name: str = None) -> None:
        if tab_name:
            if stopped:
                self._stopped_tabs.add(tab_name)
            else:
                self._stopped_tabs.discard(tab_name)
        else:
            self._stopped = stopped
            if stopped:
                self._stopped_tabs.clear()
    
    def is_stopped(self, tab_name: str = None) -> bool:
        if tab_name:
            return tab_name in self._stopped_tabs
        return self._stopped
    
    def clear_tab_entries(self, tab_name: str) -> None:
        with self._buffer_lock:
            self._buffer = [
                entry for entry in self._buffer
                if entry.tab_name != tab_name or entry.level not in (LogLevel.SUCCESS, LogLevel.FAILURE)
            ]
    
    def clear_success_failure_entries(self) -> None:
        """清除缓冲区中的成功和失败日志条目
        
        在停止运行时调用，清除可能因竞态条件残留的成功/失败日志，
        避免用户看到停止瞬间的误导性成功日志。
        """
        with self._buffer_lock:
            self._buffer = [
                entry for entry in self._buffer
                if entry.level not in (LogLevel.SUCCESS, LogLevel.FAILURE)
            ]
    
    def flush(self) -> List[LogEntry]:
        with self._buffer_lock:
            entries = self._buffer.copy()
            self._buffer.clear()
            return entries
    
    def clear(self) -> None:
        with self._buffer_lock:
            self._buffer.clear()
    
    def get_buffer_size(self) -> int:
        with self._buffer_lock:
            return len(self._buffer)
