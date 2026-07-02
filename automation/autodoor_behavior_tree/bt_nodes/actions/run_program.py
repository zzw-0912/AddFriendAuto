import subprocess
import time
import os
import sys
import signal
from typing import Dict, Any, Optional

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


class RunProgramNode(ActionNode):
    NODE_TYPE = "RunProgramNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.program_path = self.config.get("program_path", "")
        self.arguments = self.config.get("arguments", "")
        self.working_dir = self.config.get("working_dir", "")
        self.wait_complete = self.config.get_bool("wait_complete", False)
        self.timeout_ms = self.config.get_int("timeout_ms", 0)
        self._process: Optional[subprocess.Popen] = None
        self._start_time: Optional[float] = None

    def _execute_action(self, context) -> NodeStatus:
        if self._process is None:
            program = self.config.get("program_path", self.program_path)
            if not program:
                LogManager.instance().log_info("运行程序", self.name, "程序路径为空")
                return NodeStatus.FAILURE

            args = self.config.get("arguments", self.arguments)
            work_dir = self.config.get("working_dir", self.working_dir)
            wait = self.config.get_bool("wait_complete", self.wait_complete)
            self.timeout_ms = self.config.get_int("timeout_ms", self.timeout_ms)

            cmd = [program]
            if args:
                cmd.extend(args.split())

            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

                self._process = subprocess.Popen(
                    cmd,
                    cwd=work_dir if work_dir else None,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
            except Exception as e:
                LogManager.instance().log_failure("运行程序", self.name, f"启动失败: {e}")
                self._show_error(f"无法启动程序:\n{program}\n\n错误信息: {e}")
                self._process = None
                return NodeStatus.FAILURE

            self._start_time = time.time()
            LogManager.instance().log_info("运行程序", self.name, f"已启动: {program}")

            if not wait:
                self._process = None
                self._start_time = None
                return NodeStatus.SUCCESS

        if self._process is None:
            return NodeStatus.SUCCESS

        rc = self._process.poll()
        if rc is not None:
            self._process = None
            self._start_time = None
            if rc == 0:
                LogManager.instance().log_success("运行程序", self.name)
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure("运行程序", self.name, f"退出码: {rc}")
                return NodeStatus.FAILURE

        if self.timeout_ms > 0:
            elapsed = (time.time() - self._start_time) * 1000
            if elapsed >= self.timeout_ms:
                self._terminate_process()
                LogManager.instance().log_failure("运行程序", self.name, "超时")
                return NodeStatus.FAILURE

        return NodeStatus.RUNNING

    def _show_error(self, message: str):
        try:
            from tkinter import messagebox
            messagebox.showerror("运行程序 - 启动失败", message)
        except Exception:
            pass

    def _terminate_process(self):
        if self._process is not None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            except Exception:
                pass
            self._process = None
            self._start_time = None

    def abort(self, context) -> None:
        self._terminate_process()
        super().abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        self._terminate_process()
        super().reset(reset_counters=reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunProgramNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
