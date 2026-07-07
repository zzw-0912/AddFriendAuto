import time
import threading
from typing import List, Callable, Optional

from pynput import mouse, keyboard
from .key_name_resolver import resolve_key_name


class ScriptRecorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._is_recording = False
        self.events: List[dict] = []
        self.start_time: float = 0
        self.last_event_time: float = 0
        self.pressed_keys = set()

        self.keyboard_listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None
        self._on_event: Optional[Callable] = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def start_recording(self) -> None:
        with self._lock:
            self._is_recording = True
            self.events = []
            self.start_time = time.time()
            self.last_event_time = self.start_time
            self.pressed_keys = set()

        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click
        )

        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop_recording(self) -> List[dict]:
        with self._lock:
            self._is_recording = False

        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

        with self._lock:
            return list(self.events)

    def save_to_file(self, filepath: str) -> None:
        """保存录制到脚本文件

        Args:
            filepath: 文件路径
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            for event in self.events:
                f.write(self._format_event(event) + '\n')

    def _on_key_press(self, key):
        with self._lock:
            if not self._is_recording:
                return

            key_name = self._get_key_name(key)
            if key_name and key_name not in self.pressed_keys:
                self._add_delay()
                self.events.append({
                    "type": "keydown",
                    "key": key_name
                })
                self.pressed_keys.add(key_name)

                if self._on_event:
                    self._on_event(self.events[-1])

    def _on_key_release(self, key):
        with self._lock:
            if not self._is_recording:
                return

            key_name = self._get_key_name(key)
            if key_name and key_name in self.pressed_keys:
                self._add_delay()
                self.events.append({
                    "type": "keyup",
                    "key": key_name
                })
                self.pressed_keys.remove(key_name)

    def _on_mouse_move(self, x, y):
        pass

    def _on_mouse_click(self, x, y, button, pressed):
        with self._lock:
            if not self._is_recording:
                return

            self._add_delay()

            self.events.append({
                "type": "moveto",
                "x": x,
                "y": y
            })

            self.events.append({
                "type": f"mouse_{'down' if pressed else 'up'}",
                "button": button.name
            })

    def _add_delay(self):
        current_time = time.time()
        delay = int((current_time - self.last_event_time) * 1000)
        if delay > 0:
            self.events.append({
                "type": "delay",
                "time": delay
            })
        self.last_event_time = current_time

    def _get_key_name(self, key) -> str:
        return resolve_key_name(key)

    def _format_event(self, event: dict) -> str:
        if event["type"] == "delay":
            return f"Delay {event['time']}"
        elif event["type"] == "keydown":
            return f'KeyDown "{event["key"]}", 1'
        elif event["type"] == "keyup":
            return f'KeyUp "{event["key"]}", 1'
        elif event["type"] == "moveto":
            return f"MoveTo {event['x']}, {event['y']}"
        elif event["type"] == "mouse_down":
            button = event["button"].capitalize()
            return f"{button}Down 1"
        elif event["type"] == "mouse_up":
            button = event["button"].capitalize()
            return f"{button}Up 1"
        return ""
