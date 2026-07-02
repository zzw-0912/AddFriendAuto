import customtkinter as ctk
from typing import Callable, Optional, Dict


class TabButton(ctk.CTkFrame):
    """Tab 按钮组件
    
    包含运行/停止按钮、名称标签、状态指示器、关闭按钮
    """
    ICON_RUN = "\u25b6"
    ICON_STOP = "\u25a0"
    ICON_CLOSE = "\u2715"

    def __init__(self, master, tab_id: str, name: str,
                 on_run_stop: Optional[Callable[[str, bool], None]] = None,
                 on_close: Optional[Callable[[str], None]] = None,
                 on_click: Optional[Callable[[str], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self.tab_id = tab_id
        self._name = name
        self._is_running = False
        self._is_active = False

        self._on_run_stop = on_run_stop
        self._on_close = on_close
        self._on_click = on_click

        self._create_widgets()

    def _create_widgets(self):
        self._run_stop_btn = ctk.CTkButton(
            self,
            text=self.ICON_RUN,
            width=24,
            height=24,
            font=("Arial", 10),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self._on_run_stop_click
        )
        self._run_stop_btn.pack(side="left", padx=2)

        self._name_label = ctk.CTkLabel(
            self,
            text=self._name,
            font=("Microsoft YaHei", 11),
            cursor="hand2"
        )
        self._name_label.pack(side="left", padx=4, fill="x", expand=True)
        self._name_label.bind("<Button-1>", self._on_name_click)

        self._status_indicator = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 8),
            text_color="#22c55e"
        )
        self._status_indicator.pack(side="left", padx=2)

        self._close_btn = ctk.CTkButton(
            self,
            text=self.ICON_CLOSE,
            width=20,
            height=20,
            font=("Arial", 8),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "gray90"),
            command=self._on_close_click
        )
        self._close_btn.pack(side="right", padx=2)

        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.configure(fg_color=("gray75", "gray25"))
            self._name_label.configure(font=("Microsoft YaHei", 11, "bold"))
        else:
            self.configure(fg_color="transparent")
            self._name_label.configure(font=("Microsoft YaHei", 11))

        if self._is_running:
            self._run_stop_btn.configure(text=self.ICON_STOP, text_color="#22c55e")
            self._status_indicator.configure(text="\u2022")
        else:
            self._run_stop_btn.configure(text=self.ICON_RUN, text_color=("gray10", "gray90"))
            self._status_indicator.configure(text="")

    def _on_run_stop_click(self):
        if self._on_run_stop:
            self._on_run_stop(self.tab_id, not self._is_running)

    def _on_close_click(self):
        if self._on_close:
            self._on_close(self.tab_id)

    def _on_name_click(self, event):
        if self._on_click:
            self._on_click(self.tab_id)

    def set_running(self, running: bool):
        self._is_running = running
        self._update_style()

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    @property
    def name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name
        self._name_label.configure(text=name)


class TabBar(ctk.CTkFrame):
    """Tab 栏容器
    
    管理多个 TabButton，提供 Tab 切换、关闭、运行控制
    """
    
    def __init__(self, master,
                 on_tab_switch: Optional[Callable[[str], None]] = None,
                 on_tab_close: Optional[Callable[[str], None]] = None,
                 on_tab_run: Optional[Callable[[str], None]] = None,
                 on_tab_stop: Optional[Callable[[str], None]] = None,
                 on_import: Optional[Callable[[], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self._tab_buttons: Dict[str, TabButton] = {}
        self._active_tab_id: Optional[str] = None

        self._on_tab_switch = on_tab_switch
        self._on_tab_close = on_tab_close
        self._on_tab_run = on_tab_run
        self._on_tab_stop = on_tab_stop
        self._on_import = on_import

        self._create_widgets()

    def _create_widgets(self):
        self._tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._tabs_frame.pack(side="left", fill="x", expand=True)
        
        self._add_btn = ctk.CTkButton(
            self._tabs_frame,
            text="+",
            width=28,
            height=28,
            font=("Arial", 14),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "gray90"),
            command=self._on_import_click
        )
        self._add_btn.pack(side="left", padx=2, pady=4)

    def _on_import_click(self):
        if self._on_import:
            self._on_import()

    def add_tab(self, tab_id: str, name: str) -> None:
        btn = TabButton(
            self._tabs_frame,
            tab_id=tab_id,
            name=name,
            on_run_stop=self._handle_run_stop,
            on_close=self._handle_close,
            on_click=self._handle_click
        )
        btn.pack(side="left", padx=2, pady=4, before=self._add_btn)
        self._tab_buttons[tab_id] = btn

        if self._active_tab_id is None:
            self.set_active(tab_id)

    def remove_tab(self, tab_id: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].destroy()
            del self._tab_buttons[tab_id]

            if self._active_tab_id == tab_id:
                tab_ids = list(self._tab_buttons.keys())
                self._active_tab_id = tab_ids[0] if tab_ids else None
                if self._active_tab_id:
                    self.set_active(self._active_tab_id)

    def set_active(self, tab_id: str) -> None:
        for tid, btn in self._tab_buttons.items():
            btn.set_active(tid == tab_id)
        self._active_tab_id = tab_id

    def set_running(self, tab_id: str, running: bool) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_running(running)

    def _handle_run_stop(self, tab_id: str, should_run: bool):
        if should_run:
            if self._on_tab_run:
                self._on_tab_run(tab_id)
        else:
            if self._on_tab_stop:
                self._on_tab_stop(tab_id)

    def _handle_close(self, tab_id: str):
        if self._on_tab_close:
            self._on_tab_close(tab_id)

    def _handle_click(self, tab_id: str):
        if self._on_tab_switch:
            self._on_tab_switch(tab_id)

    def update_tab_name(self, tab_id: str, name: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_name(name)

    def get_tab_count(self) -> int:
        return len(self._tab_buttons)
    
    @property
    def active_tab_id(self) -> Optional[str]:
        return self._active_tab_id
