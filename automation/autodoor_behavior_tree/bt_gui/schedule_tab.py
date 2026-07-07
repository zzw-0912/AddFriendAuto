import customtkinter as ctk
import os
import json
import threading
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox
from typing import Optional

from .theme import Theme
from bt_core.serializer import Serializer
from bt_core.engine import BehaviorTreeEngine
from bt_core.context import ExecutionContext
from bt_utils.log_manager import LogManager


class ScheduleTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._dark_colors = Theme.get_dark_colors()

        self._schedule_running = False
        self._cancelled = False
        self._current_run = 0
        self._total_runs = 0
        self._success_count = 0
        self._failure_count = 0
        self._current_engine: Optional[BehaviorTreeEngine] = None
        self._poll_job = None

        self._create_ui()

    def _create_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Left – Config ──
        left = ctk.CTkFrame(self, fg_color=self._dark_colors['bg_secondary'],
                            corner_radius=Theme.DIMENSIONS['card_corner_radius'])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_columnconfigure(1, weight=1)

        r = 0
        ctk.CTkLabel(left, text="⏰ 定时执行", font=Theme.get_font('lg'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(15, 15), padx=15)
        r += 1

        # File
        ctk.CTkLabel(left, text="文件选择", font=Theme.get_font('sm'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        r += 1

        ff = ctk.CTkFrame(left, fg_color="transparent")
        ff.grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        ff.grid_columnconfigure(0, weight=1)
        self.file_entry = ctk.CTkEntry(ff, placeholder_text="选择行为树文件...",
                                        font=Theme.get_font('sm'), height=Theme.DIMENSIONS['input_height'])
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkButton(ff, text="浏览", width=60, height=Theme.DIMENSIONS['input_height'],
                       font=Theme.get_font('sm'), command=self._browse_file
        ).grid(row=0, column=1)
        r += 1

        ctk.CTkFrame(left, height=1, fg_color=self._dark_colors['border']
        ).grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        r += 1

        # Time
        ctk.CTkLabel(left, text="执行时间", font=Theme.get_font('sm'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        r += 1

        tf = ctk.CTkFrame(left, fg_color="transparent")
        tf.grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        now = datetime.now()
        labels = ["年", "月", "日", "时", "分", "秒"]
        defaults = [str(now.year), f"{now.month:02d}", f"{now.day:02d}",
                    f"{now.hour:02d}", f"{now.minute:02d}", "00"]
        self._time_entries = {}
        for i, (lbl, dft) in enumerate(zip(labels, defaults)):
            ctk.CTkLabel(tf, text=lbl, font=Theme.get_font('xs'),
                          text_color=self._dark_colors['text_muted']
            ).grid(row=0, column=i*2, padx=(0, 2))
            e = ctk.CTkEntry(tf, width=50, height=Theme.DIMENSIONS['input_height'],
                              font=Theme.get_font('sm'), justify="center")
            e.insert(0, dft)
            e.grid(row=0, column=i*2+1, padx=(0, 8 if i < len(labels)-1 else 0))
            self._time_entries[lbl] = e
        r += 1

        ctk.CTkFrame(left, height=1, fg_color=self._dark_colors['border']
        ).grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        r += 1

        # Config
        ctk.CTkLabel(left, text="执行配置", font=Theme.get_font('sm'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        r += 1

        cf = ctk.CTkFrame(left, fg_color="transparent")
        cf.grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        ctk.CTkLabel(cf, text="执行次数:", font=Theme.get_font('sm'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=0, column=0, padx=(0, 5))
        self.count_entry = ctk.CTkEntry(cf, width=60, height=Theme.DIMENSIONS['input_height'],
                                         font=Theme.get_font('sm'), justify="center")
        self.count_entry.insert(0, "5")
        self.count_entry.grid(row=0, column=1, padx=(0, 15))
        ctk.CTkLabel(cf, text="间隔(分钟):", font=Theme.get_font('sm'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=0, column=2, padx=(0, 5))
        self.interval_entry = ctk.CTkEntry(cf, width=60, height=Theme.DIMENSIONS['input_height'],
                                            font=Theme.get_font('sm'), justify="center")
        self.interval_entry.insert(0, "1")
        self.interval_entry.grid(row=0, column=3)
        r += 1

        # Buttons
        bf = ctk.CTkFrame(left, fg_color="transparent")
        bf.grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 5))
        self.start_btn = ctk.CTkButton(bf, text="▶ 开始调度", width=100, height=32,
                                        font=Theme.get_font('sm'),
                                        fg_color=self._dark_colors['primary'],
                                        hover_color=self._dark_colors['primary_hover'],
                                        command=self._start_schedule)
        self.start_btn.pack(side="left", padx=(0, 10))
        self.cancel_btn = ctk.CTkButton(bf, text="⏹ 取消调度", width=100, height=32,
                                         font=Theme.get_font('sm'),
                                         fg_color=self._dark_colors['bg_tertiary'],
                                         hover_color=self._dark_colors['border'],
                                         state="disabled", command=self._cancel_schedule)
        self.cancel_btn.pack(side="left")
        r += 1

        self.status_label = ctk.CTkLabel(left, text="状态: 就绪", font=Theme.get_font('sm'),
                                          text_color=self._dark_colors['text_muted'], anchor="w")
        self.status_label.grid(row=r, column=0, columnspan=2, sticky="ew", padx=15, pady=(5, 15))

        # ── Right – Log ──
        right = ctk.CTkFrame(self, fg_color=self._dark_colors['bg_secondary'],
                              corner_radius=Theme.DIMENSIONS['card_corner_radius'])
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="定时执行日志", font=Theme.get_font('lg'),
                      text_color=self._dark_colors['text_primary']
        ).grid(row=0, column=0, sticky="w", pady=(15, 10), padx=15)

        self.log_text = ctk.CTkTextbox(right, font=Theme.get_font('sm'),
                                        fg_color=self._dark_colors['bg_primary'],
                                        text_color=self._dark_colors['text_primary'], wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_text.configure(state="disabled")

    # ── helpers ──

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str):
        self.status_label.configure(text=f"状态: {text}")

    def _set_ui_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.file_entry.configure(state=state)
        self.browse_btn.configure(state=state)
        for e in self._time_entries.values():
            e.configure(state=state)
        self.count_entry.configure(state=state)
        self.interval_entry.configure(state=state)

    def _browse_file(self):
        path = filedialog.askopenfilename(title="选择行为树文件",
                                           filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)

    def _parse_datetime(self) -> Optional[datetime]:
        try:
            parts = []
            for lbl in ["年", "月", "日", "时", "分", "秒"]:
                val = self._time_entries[lbl].get().strip()
                parts.append(int(val))
            return datetime(*parts)
        except (ValueError, TypeError):
            return None

    # ── schedule control ──

    def _start_schedule(self):
        file_path = self.file_entry.get().strip()
        if not file_path:
            messagebox.showwarning("提示", "请选择行为树文件")
            return
        if not os.path.isfile(file_path):
            messagebox.showerror("错误", f"文件不存在:\n{file_path}")
            return

        target = self._parse_datetime()
        if not target:
            messagebox.showwarning("提示", "请输入有效的日期时间")
            return
        if target <= datetime.now():
            messagebox.showwarning("提示", "执行时间必须在当前时间之后")
            return

        try:
            self._total_runs = int(self.count_entry.get().strip())
            if self._total_runs < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "执行次数必须为正整数")
            return

        try:
            self._interval_minutes = int(self.interval_entry.get().strip())
            if self._interval_minutes < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "间隔时间必须为非负整数")
            return

        self._schedule_running = True
        self._cancelled = False
        self._current_run = 0
        self._success_count = 0
        self._failure_count = 0
        self._target_time = target
        self._schedule_file = file_path

        self._set_ui_enabled(False)
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        self._log(f"调度已启动")
        self._log(f"目标文件: {file_path}")
        self._log(f"执行时间: {target.strftime('%Y-%m-%d %H:%M:%S')}")
        self._log(f"执行次数: {self._total_runs} 次")
        self._log(f"间隔时间: {self._interval_minutes} 分钟")
        self._log("")

        self._poll()

    def _cancel_schedule(self):
        self._cancelled = True
        self._schedule_running = False
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self._current_engine:
            try:
                self._current_engine.stop()
            except Exception:
                pass
            self._current_engine = None
        self._log("")
        self._log("调度已取消")
        self._finish()

    def _poll(self):
        if self._cancelled or not self._schedule_running:
            return
        now = datetime.now()
        remaining = (self._target_time - now).total_seconds()
        if remaining <= 0:
            self._log(f"到达执行时间，开始运行...")
            self._set_status("执行中...")
            self._run_next()
            return
        self._set_status(f"等待中 (剩余 {int(remaining)} 秒)")
        self._poll_job = self.after(1000, self._poll)

    def _run_next(self):
        if self._cancelled or not self._schedule_running:
            return
        if self._current_run >= self._total_runs:
            self._show_summary()
            return

        self._current_run += 1
        current = self._current_run
        self._log(f"── 第 {current}/{self._total_runs} 次运行 ──")

        file_path = self._schedule_file
        if not os.path.isfile(file_path):
            self._log(f"[错误] 文件不存在: {file_path}")
            self._failure_count += 1
            self._finish()
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except Exception as e:
            self._log(f"[错误] 读取文件失败: {e}")
            self._failure_count += 1
            self._finish()
            return

        try:
            root = Serializer.deserialize(raw)
            if isinstance(root, tuple):
                root = root[0]
        except Exception as e:
            self._log(f"[错误] 解析行为树失败: {e}")
            self._failure_count += 1
            self._finish()
            return

        if not root:
            self._log("[错误] 行为树为空")
            self._failure_count += 1
            self._finish()
            return

        project_root = os.path.dirname(file_path)
        context = ExecutionContext(project_root=project_root)
        engine = BehaviorTreeEngine(root)
        engine._on_status_change = lambda status, ns=None, cur=current: \
            self.after(0, self._on_run_done, status, cur)
        self._current_engine = engine

        engine.start(context)

    def _on_run_done(self, status: str, run_number: int):
        self._current_engine = None
        if self._cancelled:
            return

        if status == "completed":
            self._success_count += 1
            self._log(f"第 {run_number} 次运行: 成功")
        else:
            self._failure_count += 1
            self._log(f"第 {run_number} 次运行: {status}")

        if self._cancelled or not self._schedule_running:
            return

        if self._current_run >= self._total_runs:
            self._show_summary()
            return

        interval_ms = self._interval_minutes * 60 * 1000
        self._log(f"等待 {self._interval_minutes} 分钟后执行下一次...")
        self._set_status(f"等待 {self._interval_minutes} 分钟")
        self.after(interval_ms, self._run_next)

    def _show_summary(self):
        self._schedule_running = False
        total = self._success_count + self._failure_count
        self._log("")
        self._log("═" * 30)
        self._log(f"执行完成: {total}/{self._total_runs} 次")
        self._log(f"成功 {self._success_count} 次, 失败 {self._failure_count} 次")
        if self._failure_count > 0:
            LogManager.instance().log_info("系统", "", f"定时执行完成: {total} 次, 成功 {self._success_count}, 失败 {self._failure_count}")
        self._finish()

    def _finish(self):
        self._schedule_running = False
        self._current_engine = None
        self._set_ui_enabled(True)
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        if not self._cancelled:
            self._set_status("已完成")
