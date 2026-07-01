import threading
from queue import Queue, Empty
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
from enum import Enum
from bt_utils.singleton import singleton
from bt_utils.log_manager import LogManager


class UpdateType(Enum):
    NODE_STATUS = "node_status"
    LOG_FLUSH = "log_flush"
    CANVAS_REDRAW = "canvas_redraw"
    ENGINE_STATUS = "engine_status"


@dataclass
class UpdateTask:
    update_type: UpdateType
    data: Any
    callback: Callable


@singleton
class UIUpdateDispatcher:
    # 轮询间隔配置：运行时高频，空闲时低频
    POLLING_INTERVAL_RUNNING = 10    # 引擎运行时：10ms高频轮询
    POLLING_INTERVAL_IDLE = 100      # 空闲时：100ms低频轮询

    def __init__(self):
        self._task_queue: Queue = Queue()
        self._widget = None
        self._polling_active = False
        self._polling_interval_ms = self.POLLING_INTERVAL_IDLE
        self._max_batch_size = 50
        self._engine_running = False
    
    @classmethod
    def reset_instance(cls):
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None
    
    def attach(self, widget):
        self._widget = widget
        widget.bind("<<UIUpdate>>", self._process_updates)
    
    def detach(self):
        if self._widget:
            self._widget.unbind("<<UIUpdate>>")
            self._widget = None
    
    def dispatch(self, update_type: UpdateType, data: Any = None, callback: Callable = None):
        task = UpdateTask(update_type, data, callback)
        self._task_queue.put(task)
        
        self._schedule_process()
    
    def dispatch_node_status(self, node_id: str, status: str, callback: Callable = None):
        task = UpdateTask(UpdateType.NODE_STATUS, {"node_id": node_id, "status": status}, callback)
        self._task_queue.put(task)
        
        self._schedule_process()
    
    def dispatch_log_flush(self):
        task = UpdateTask(UpdateType.LOG_FLUSH, None, None)
        self._task_queue.put(task)
        self._schedule_process()
    
    def dispatch_engine_status(self, status: str, node_status: Any = None, callback: Callable = None):
        task = UpdateTask(UpdateType.ENGINE_STATUS, {"status": status, "node_status": node_status}, callback)
        self._task_queue.put(task)
        self._schedule_process()

        # 自适应轮询间隔：引擎运行时高频，空闲时低频
        is_running = status in ("running", "paused")
        if is_running != self._engine_running:
            self._engine_running = is_running
            self._polling_interval_ms = (
                self.POLLING_INTERVAL_RUNNING if is_running
                else self.POLLING_INTERVAL_IDLE
            )

    def set_engine_running(self, running: bool):
        """手动设置引擎运行状态，用于自适应调整轮询间隔

        Args:
            running: 引擎是否正在运行
        """
        self._engine_running = running
        self._polling_interval_ms = (
            self.POLLING_INTERVAL_RUNNING if running
            else self.POLLING_INTERVAL_IDLE
        )
    
    def _schedule_process(self):
        pass
    
    def _process_updates_safe(self):
        try:
            self._process_updates()
        except Exception as e:
            LogManager.debug_print(f"[WARN] UI更新处理失败: {e}")
    
    def _process_updates(self, event=None):
        processed = 0
        
        while processed < self._max_batch_size:
            try:
                task = self._task_queue.get_nowait()
                
                if task.callback:
                    try:
                        if task.update_type == UpdateType.NODE_STATUS and task.data:
                            task.callback(task.data.get("node_id"), task.data.get("status"))
                        else:
                            task.callback(task.data)
                    except Exception as e:
                        LogManager.debug_print(f"[WARN] UI更新回调执行失败: {e}")
                
                processed += 1
                
            except Empty:
                break
        
        if not self._task_queue.empty():
            if self._widget:
                self._widget.after(10, self._process_updates_safe)
    
    def process_pending(self):
        self._process_updates()
    
    def get_pending_count(self) -> int:
        return self._task_queue.qsize()
    
    def clear_all(self):
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
            except Empty:
                break
    
    def start_polling(self):
        if self._polling_active and self._widget is not None:
            return
        
        self._polling_active = True
        self._poll()
    
    def stop_polling(self):
        self._polling_active = False
    
    def _poll(self):
        if not self._polling_active:
            return
        
        widget = self._widget
        
        try:
            if widget is not None:
                pending = self._task_queue.qsize()
                if pending > 0:
                    self._process_updates()
        except Exception as e:
            LogManager.debug_print(f"[DEBUG] UI轮询处理异常: {e}")
        
        if self._polling_active:
            try:
                if self._widget is not None:
                    self._widget.after(self._polling_interval_ms, self._poll)
                else:
                    threading.Timer(self._polling_interval_ms / 1000, self._poll_daemon).start()
            except Exception as e:
                LogManager.debug_print(f"[DEBUG] UI轮询调度异常: {e}")
                threading.Timer(self._polling_interval_ms / 1000, self._poll_daemon).start()
    
    def _poll_daemon(self):
        """后台线程轮询，用于在 _widget 为 None 时继续尝试"""
        if self._polling_active and self._widget is not None:
            try:
                self._widget.after(0, self._poll)
            except Exception:
                threading.Timer(self._polling_interval_ms / 1000, self._poll_daemon).start()
        elif self._polling_active:
            threading.Timer(self._polling_interval_ms / 1000, self._poll_daemon).start()


def get_dispatcher() -> UIUpdateDispatcher:
    return UIUpdateDispatcher()
