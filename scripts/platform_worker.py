"""
FriendAuto AutoDoor worker.

Reads a task JSON from stdin, prepares a per-run copy of an AutoDoor project,
patches runtime options into the copied behavior tree, runs it through the
AutoDoor source engine, and prints FriendAuto ScriptEvent JSON lines to stdout.
"""

from __future__ import annotations

import contextlib
import email.charset
import email.errors
import email.feedparser
import email.header
import email.message
import email.parser
import email.policy
import email.utils
import http.client
import http.cookiejar
import http.cookies
import importlib
import io
import json
import mimetypes
import netrc
import os
import random
import re
import shutil
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


LEGACY_AUTODOOR_SOURCE_PATH = r"D:\AddFriend\autodoor_behavior_tree"
LEGACY_PROJECT_PATH = r"D:\AddFriend\Addfriend"
LEGACY_EDITOR_EXECUTABLE_PATH = (
    r"D:\AddFriend\autodoor_behavior_tree\dist\autodoor-behaviortree-1.6.0"
    r"\autodoor-behaviortree-1.6.0.exe"
)
CONFIG_FILE_NAME = "autodoor.json"
PROJECT_COPY_NAME = "Addfriend"
STOP_REQUEST_DIR_NAME = "stop_requests"
PHONE_INPUT_KEYWORDS = ["输入手机号", "手机号"]
WECHAT_ID_INPUT_KEYWORDS = ["输入微信号", "微信号"]
GREETING_KEYWORDS = ["输入申请语", "申请语"]
VALIDATION_KEYWORDS = ["判断是否输入正确", "输入正确"]
CONFIRM_CLICK_KEYWORDS = ["点击确定", "确定"]
KEY_FAILURE_KEYWORDS = ["发送添加好友申请", "添加到通讯录", "输入申请语"]
ADD_TO_CONTACTS_KEYWORDS = ["添加到通讯录"]
SEARCH_CLEANUP_KEYWORDS = ["叉", "点击叉"]
CLOSE_FRIEND_WINDOW_KEYWORDS = ["点击叉", "关闭"]
WECHAT_START_KEYWORDS = ["微信", "添加朋友", "申请添加朋友"]
ALREADY_FRIEND_KEYWORDS = ["发消息", "语音聊天", "视频聊天"]
SEARCH_RESULT_RETRY_COUNT = 8
SEARCH_RESULT_RETRY_INTERVAL_MS = 500
BOOTSTRAP_MAX_ATTEMPTS = 2
BOOTSTRAP_RETRY_MAX_SECONDS = 8.0
BOOTSTRAP_RETRY_DELAY_SECONDS = 2.0
REPEATED_TARGET_INPUT_ABORT_COUNT = 4
TARGET_RUN_TIMEOUT_SECONDS = 180.0
AUTOMATION_LOCK_FILE_NAME = "automation.lock"
CLIPBOARD_LOCK_FILE_NAME = "clipboard.lock"
ACCOUNT_AGE_INTERVALS_MS = {
    "new": (25 * 60 * 1000, 5 * 60 * 1000),
    "mid": (1050 * 1000, 150 * 1000),
    "old": (450 * 1000, 150 * 1000),
}
DEFAULT_ACCOUNT_AGE_PROFILE = "new"
DEFAULT_GREETING_TEXT = "你好，很高兴认识你，方便加个微信交流一下吗？"
MOJIBAKE_HINTS = (
    "浣", "佸", "涔", "涓", "鍙", "鎴", "鏂", "妯", "瀷", "鎼", "储",
    "棰", "勮", "椤", "哄", "簭", "鐢", "宠", "濂", "藉", "弸",
    "涴", "銪", "鑰", "鐩", "逛", "绠", "钀", "ㄣ", "�",
)


@dataclass
class RunOutcome:
    phone_started: bool
    total_finished: int
    success_count: int
    failed_count: int
    invalid_count: int
    elapsed_seconds: float


@dataclass
class PreparedTarget:
    target_id: int | None
    target_type: str
    target_value: str
    display_name: str = ""


@dataclass
class AutoDoorConfig:
    autodoor_source_path: str
    project_path: str
    editor_executable_path: str = ""


@dataclass
class PreparedRun:
    run_dir: Path
    project_dir: Path
    tree_file: Path
    base_tree_file: Path
    target_type: str
    targets: list[PreparedTarget]
    phone_numbers: list[str]
    phone_input_ids: set[str]
    validation_ids: set[str]
    not_found_ids: set[str]
    confirm_click_ids: set[str]
    success_close_ids: set[str]
    key_failure_ids: set[str]


_emit_lock = threading.Lock()
_dll_directory_handles: list[Any] = []
AUTODOOR_EXTERNAL_MODULE_PREFIXES = (
    "PIL",
    "cv2",
    "numpy",
    "rapidocr",
    "onnxruntime",
    "bt_core",
    "bt_nodes",
    "bt_utils",
    "pyautogui",
    "pyscreeze",
    "pyclipper",
    "shapely",
)


class StopRequested(Exception):
    pass


def runtime_base_dirs() -> list[Path]:
    bases: list[Path] = []
    runtime_dir = os.environ.get("FRIENDAUTO_RUNTIME_DIR")
    if runtime_dir:
        bases.append(Path(runtime_dir))
    for base in [Path(__file__).resolve().parents[1], Path.cwd(), Path(sys.executable).resolve().parent]:
        bases.append(base)
        bases.extend(base.parents[:2])

    unique: list[Path] = []
    seen: set[str] = set()
    for base in bases:
        key = str(base).lower()
        if key not in seen:
            seen.add(key)
            unique.append(base)
    return unique


def autodoor_editor_path(source_path: Path) -> str:
    preferred = (
        source_path
        / "dist"
        / "autodoor-behaviortree-1.6.0"
        / "autodoor-behaviortree-1.6.0.exe"
    )
    return str(preferred) if preferred.is_file() else ""


def local_autodoor_config() -> AutoDoorConfig | None:
    append_worker_log(
        "local_autodoor_config scan_start",
        base_dirs=[str(path) for path in runtime_base_dirs()],
    )
    for base in runtime_base_dirs():
        for root in [base / "automation", base]:
            source_path = root / "autodoor_behavior_tree"
            project_path = root / "Addfriend"
            append_worker_log(
                "local_autodoor_config check",
                base=str(base),
                root=str(root),
                source_path=str(source_path),
                source_exists=source_path.is_dir(),
                project_path=str(project_path),
                project_exists=project_path.is_dir(),
            )
            if source_path.is_dir() and project_path.is_dir():
                append_worker_log(
                    "local_autodoor_config selected",
                    source_path=str(source_path),
                    project_path=str(project_path),
                    editor_executable_path=autodoor_editor_path(source_path),
                )
                return AutoDoorConfig(
                    autodoor_source_path=str(source_path),
                    project_path=str(project_path),
                    editor_executable_path=autodoor_editor_path(source_path),
                )
    append_worker_log("local_autodoor_config not_found")
    return None


def legacy_autodoor_config() -> AutoDoorConfig:
    return AutoDoorConfig(
        autodoor_source_path=LEGACY_AUTODOOR_SOURCE_PATH,
        project_path=LEGACY_PROJECT_PATH,
        editor_executable_path=LEGACY_EDITOR_EXECUTABLE_PATH,
    )


def default_autodoor_config() -> AutoDoorConfig:
    return local_autodoor_config() or legacy_autodoor_config()


def is_legacy_path(value: str, legacy: str) -> bool:
    return value.strip().lower() == legacy.lower()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def has_surrogate_char(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def strip_surrogate_chars(text: str) -> str:
    if not has_surrogate_char(text):
        return text
    return "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)


def count_surrogate_chars(value: Any) -> int:
    if isinstance(value, str):
        return sum(1 for ch in value if 0xD800 <= ord(ch) <= 0xDFFF)
    if isinstance(value, list):
        return sum(count_surrogate_chars(item) for item in value)
    if isinstance(value, dict):
        return sum(count_surrogate_chars(key) + count_surrogate_chars(item) for key, item in value.items())
    return 0


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_surrogate_chars(value)
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_json_value(key) if isinstance(key, str) else key: sanitize_json_value(item)
            for key, item in value.items()
        }
    return value


def looks_like_mojibake(text: str) -> bool:
    if not text:
        return False
    if has_surrogate_char(text) or "\ufffd" in text:
        return True
    hits = sum(1 for hint in MOJIBAKE_HINTS if hint and hint in text)
    return hits >= 2


def repair_mojibake_text(text: str) -> str:
    if not text:
        return ""
    candidates: list[str] = []
    for encoding in ("gbk", "gb18030"):
        try:
            candidates.append(text.encode(encoding, errors="surrogateescape").decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    for candidate in candidates:
        candidate = strip_surrogate_chars(candidate).strip()
        if candidate and not looks_like_mojibake(candidate):
            return candidate
    return ""


def normalize_greeting_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not looks_like_mojibake(text):
        return strip_surrogate_chars(text)

    repaired = repair_mojibake_text(text)
    if repaired:
        append_worker_log(
            "greeting_text_repaired",
            had_surrogates=has_surrogate_char(text),
            original_length=len(text),
            repaired_length=len(repaired),
        )
        return repaired

    append_worker_log(
        "greeting_text_fallback_default",
        had_surrogates=has_surrogate_char(text),
        original_length=len(text),
    )
    return DEFAULT_GREETING_TEXT


def normalize_task_text_fields(task_config: dict[str, Any]) -> dict[str, Any]:
    for key in ("greeting_text", "greetingText"):
        if key in task_config:
            task_config[key] = normalize_greeting_text(task_config.get(key))
    return task_config


def append_worker_log(message: str, **extra: Any) -> None:
    try:
        logs_dir = app_data_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "friendauto_worker.txt"
        payload = {
            "time": now_iso(),
            "message": message,
        }
        payload.update(extra)
        payload = sanitize_json_value(payload)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def masked_value(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def task_summary(task_config: dict[str, Any]) -> dict[str, Any]:
    targets = task_config.get("targets")
    if not isinstance(targets, list):
        targets = []
    preview = []
    for target in targets[:5]:
        if not isinstance(target, dict):
            continue
        target_value = target.get("target_value") or target.get("value") or target.get("phone") or target.get("wechat_id")
        preview.append(
            {
                "target_id": target.get("target_id") or target.get("id"),
                "target_type": target.get("target_type") or target.get("type"),
                "target_value": masked_value(target_value),
            }
        )
    return {
        "run_id": task_config.get("run_id") or task_config.get("task_id"),
        "slot_id": task_config.get("slot_id"),
        "target_type": task_config.get("target_type"),
        "target_count": len(targets),
        "targets_preview": preview,
        "has_wechat_binding": bool(task_config.get("wechat_binding")),
        "account_age_profile": task_config.get("account_age_profile"),
    }


def emit(event: str, message: str = "", **extra: Any) -> None:
    payload = {
        "event": event,
        "message": message,
        "timestamp": now_iso(),
    }
    payload.update({key: value for key, value in extra.items() if value is not None})
    payload = sanitize_json_value(payload)
    append_worker_log("emit", payload=payload)
    with _emit_lock:
        # Keep stdout ASCII-only so Rust can decode worker events even when
        # packaged Python falls back to a legacy Windows code page.
        print(json.dumps(payload, ensure_ascii=True), flush=True)


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / "AppData" / "Roaming"
    path = root / "FriendAuto"
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextlib.contextmanager
def interprocess_file_lock(lock_file_name: str):
    lock_path = app_data_dir() / lock_file_name
    handle = lock_path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)

        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    time.sleep(0.05)
        yield
    finally:
        if locked and os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


def load_config() -> AutoDoorConfig:
    config = default_autodoor_config()
    path = app_data_dir() / CONFIG_FILE_NAME
    forced_runtime_dir = os.environ.get("FRIENDAUTO_RUNTIME_DIR")
    append_worker_log(
        "load_config defaults",
        config_path=str(path),
        autodoor_source_path=config.autodoor_source_path,
        source_exists=Path(config.autodoor_source_path).is_dir(),
        project_path=config.project_path,
        project_exists=Path(config.project_path).is_dir(),
        editor_executable_path=config.editor_executable_path,
        editor_exists=Path(config.editor_executable_path).is_file() if config.editor_executable_path else False,
    )
    if not path.exists():
        return config

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if forced_runtime_dir and Path(config.autodoor_source_path).is_dir() and Path(config.project_path).is_dir():
        append_worker_log(
            "load_config forced_runtime",
            runtime_dir=forced_runtime_dir,
            autodoor_source_path=config.autodoor_source_path,
            project_path=config.project_path,
        )
        return config

    config.autodoor_source_path = str(
        raw.get("autodoorSourcePath")
        or raw.get("autodoor_source_path")
        or config.autodoor_source_path
    ).strip()
    config.project_path = str(
        raw.get("projectPath")
        or raw.get("project_path")
        or config.project_path
    ).strip()
    config.editor_executable_path = str(
        raw.get("editorExecutablePath")
        or raw.get("editor_executable_path")
        or config.editor_executable_path
    ).strip()
    defaults = default_autodoor_config()
    if (
        is_legacy_path(config.autodoor_source_path, LEGACY_AUTODOOR_SOURCE_PATH)
        and not is_legacy_path(defaults.autodoor_source_path, LEGACY_AUTODOOR_SOURCE_PATH)
    ):
        config.autodoor_source_path = defaults.autodoor_source_path
    if (
        is_legacy_path(config.project_path, LEGACY_PROJECT_PATH)
        and not is_legacy_path(defaults.project_path, LEGACY_PROJECT_PATH)
    ):
        config.project_path = defaults.project_path
    if (
        not config.editor_executable_path
        or (
            is_legacy_path(config.editor_executable_path, LEGACY_EDITOR_EXECUTABLE_PATH)
            and not is_legacy_path(defaults.editor_executable_path, LEGACY_EDITOR_EXECUTABLE_PATH)
        )
    ):
        config.editor_executable_path = defaults.editor_executable_path
    append_worker_log(
        "load_config final",
        autodoor_source_path=config.autodoor_source_path,
        source_exists=Path(config.autodoor_source_path).is_dir(),
        project_path=config.project_path,
        project_exists=Path(config.project_path).is_dir(),
        editor_executable_path=config.editor_executable_path,
        editor_exists=Path(config.editor_executable_path).is_file() if config.editor_executable_path else False,
    )
    return config


def safe_run_id(value: Any) -> str:
    text = str(value or "manual").strip()
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
    return text[:80] or "manual"


def stop_request_path(run_id: Any) -> Path:
    return app_data_dir() / STOP_REQUEST_DIR_NAME / f"{safe_run_id(run_id)}.stop"


def stop_requested(run_id: Any) -> bool:
    return bool(str(run_id or "").strip()) and stop_request_path(run_id).exists()


def raise_if_stop_requested(run_id: Any) -> None:
    if stop_requested(run_id):
        raise StopRequested()


def interruptible_sleep(seconds: float, run_id: Any, interval: float = 0.1) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        raise_if_stop_requested(run_id)
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    raise_if_stop_requested(run_id)


def contact_id_for(phone: str) -> int:
    normalized = re.sub(r"\D+", "", phone)
    return zlib.crc32(normalized.encode("utf-8")) & 0x7FFFFFFF


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone)
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return phone


def mask_target(target_type: str, value: str) -> str:
    if target_type == "phone":
        return mask_phone(value)
    text = str(value or "")
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def target_contact_id(target: PreparedTarget | None) -> int | None:
    if not target:
        return None
    if target.target_type == "phone":
        return contact_id_for(target.target_value)
    normalized = str(target.target_value or "").strip()
    if not normalized:
        return None
    return zlib.crc32(normalized.encode("utf-8")) & 0x7FFFFFFF


def target_label(target_type: str) -> str:
    if target_type == "contact":
        return "联系人"
    return "微信号" if target_type == "wechat_id" else "手机号"


def text_variants(keyword: str) -> set[str]:
    variants = {keyword}
    try:
        variants.add(keyword.encode("utf-8").decode("gbk", errors="ignore"))
    except Exception:
        pass
    try:
        variants.add(keyword.encode("utf-8").decode("cp936", errors="ignore"))
    except Exception:
        pass
    return {item for item in variants if item}


def contains_any(text: Any, keywords: list[str]) -> bool:
    haystack = str(text or "")
    return any(variant in haystack for keyword in keywords for variant in text_variants(keyword))


def node_name(node: dict[str, Any]) -> str:
    return str(node.get("name") or node.get("config", {}).get("name") or "")


def node_type(node: dict[str, Any]) -> str:
    return str(node.get("type") or "")


def node_y(node: dict[str, Any]) -> float:
    try:
        return float(node.get("position", {}).get("y", 0))
    except Exception:
        return 0.0


def get_config(node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config")
    if not isinstance(config, dict):
        config = {}
        node["config"] = config
    return config


def set_node_enabled(node: dict[str, Any], enabled: bool) -> None:
    node["enabled"] = enabled
    get_config(node)["enabled"] = enabled


def is_node_enabled(node: dict[str, Any]) -> bool:
    if node.get("enabled") is False:
        return False
    config = node.get("config")
    if isinstance(config, dict) and config.get("enabled") is False:
        return False
    return True


def parent_map(nodes: dict[str, dict[str, Any]]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for parent_id, node in nodes.items():
        for child_id in node.get("children", []) or []:
            parents[str(child_id)] = parent_id
    return parents


def walk_from(nodes: dict[str, dict[str, Any]], root_id: str | None) -> list[str]:
    if not root_id or root_id not in nodes:
        return []
    order: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen or node_id not in nodes:
            return
        seen.add(node_id)
        order.append(node_id)
        for child_id in nodes[node_id].get("children", []) or []:
            visit(str(child_id))

    visit(root_id)
    return order


def reachable_enabled_ids(nodes: dict[str, dict[str, Any]], root_id: str | None) -> list[str]:
    if not root_id or root_id not in nodes:
        return []
    order: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen or node_id not in nodes:
            return
        seen.add(node_id)
        node = nodes[node_id]
        if not is_node_enabled(node):
            return
        order.append(node_id)
        for child_id in node.get("children", []) or []:
            visit(str(child_id))

    visit(root_id)
    return order


def disable_subtree(nodes: dict[str, dict[str, Any]], node_id: str) -> None:
    if node_id not in nodes:
        return
    set_node_enabled(nodes[node_id], False)
    for child_id in nodes[node_id].get("children", []) or []:
        disable_subtree(nodes, str(child_id))


def set_children(nodes: dict[str, dict[str, Any]], parent_id: str, child_ids: list[str]) -> None:
    if parent_id in nodes:
        nodes[parent_id]["children"] = [child_id for child_id in child_ids if child_id in nodes]


def rebuild_connections(tree_data: dict[str, Any]) -> None:
    nodes = tree_data.get("nodes", {})
    connections = []
    for parent_id, node in nodes.items():
        for child_id in node.get("children", []) or []:
            if child_id in nodes:
                connections.append({"parent_id": parent_id, "child_id": child_id})
    tree_data["connections"] = connections


def normalize_phone(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalize_target_type(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"phone", "wechat_id"}:
        return text
    return "contact"


def parse_task_targets(task_config: dict[str, Any]) -> list[PreparedTarget]:
    raw_targets = task_config.get("targets")
    if not isinstance(raw_targets, list):
        raw_targets = task_config.get("contacts")
    if not isinstance(raw_targets, list):
        return []

    fallback_type = normalize_target_type(task_config.get("target_type"))
    targets: list[PreparedTarget] = []
    for item in raw_targets:
        if not isinstance(item, dict):
            continue
        value = str(item.get("target_value") or item.get("value") or item.get("phone") or item.get("wechat_id") or "").strip()
        if not value:
            continue
        target_type = normalize_target_type(item.get("target_type") or fallback_type)
        if target_type == "phone":
            value = normalize_phone(value)
            if len(value) != 11:
                raise RuntimeError(f"后端任务数据包含无效手机号: target_id={item.get('target_id')}, value='{item.get('target_value') or value}'")
        target_id_raw = item.get("target_id") or item.get("id")
        try:
            target_id = int(target_id_raw) if target_id_raw is not None else None
        except Exception:
            target_id = None
        targets.append(
            PreparedTarget(
                target_id=target_id,
                target_type=target_type,
                target_value=value,
                display_name=str(item.get("display_name") or item.get("displayName") or item.get("name") or "").strip(),
            )
        )

    target_types = {target.target_type for target in targets}
    if len(target_types) > 1:
        raise RuntimeError("同一次任务不能混合手机号和微信号")
    return targets


def validate_phone_pool(nodes: dict[str, dict[str, Any]], phone_input_ids: list[str]) -> None:
    for node_id in phone_input_ids:
        texts = get_config(nodes[node_id]).get("preset_texts", [])
        if not isinstance(texts, list):
            continue
        for index, text in enumerate(texts):
            phone = normalize_phone(text)
            if len(phone) != 11:
                raise RuntimeError(
                    f"手机号池包含无效手机号: node={node_id}, index={index}, value='{text}'"
                )


def extract_phone_pool(nodes: dict[str, dict[str, Any]], phone_input_ids: list[str]) -> list[str]:
    for node_id in phone_input_ids:
        texts = get_config(nodes[node_id]).get("preset_texts", [])
        if isinstance(texts, list) and texts:
            return [normalize_phone(item) for item in texts if normalize_phone(item)]
    return []


def parse_wechat_binding(task_config: dict[str, Any]) -> dict[str, Any] | None:
    raw = task_config.get("wechat_binding") or task_config.get("wechatBinding")
    if not isinstance(raw, dict):
        return None
    try:
        hwnd = int(raw.get("hwnd") or 0)
        pid = int(raw.get("pid") or 0)
    except Exception:
        return None
    title = str(raw.get("title") or "微信").strip() or "微信"
    display_name = str(raw.get("displayName") or raw.get("display_name") or title).strip()
    if hwnd <= 0 or pid <= 0:
        return None
    return {"hwnd": hwnd, "pid": pid, "title": title, "display_name": display_name}


def parse_add_interval_config(task_config: dict[str, Any]) -> tuple[int, int]:
    raw_profile = task_config.get("account_age_profile", task_config.get("accountAgeProfile"))
    profile = str(raw_profile or DEFAULT_ACCOUNT_AGE_PROFILE).strip()
    if profile in ACCOUNT_AGE_INTERVALS_MS:
        return ACCOUNT_AGE_INTERVALS_MS[profile]

    raw = task_config.get("add_interval_minutes", task_config.get("addIntervalMinutes"))
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        minutes = 0
    if minutes > 0:
        return minutes * 60 * 1000, 0
    return ACCOUNT_AGE_INTERVALS_MS[DEFAULT_ACCOUNT_AGE_PROFILE]


def apply_wechat_binding(nodes: dict[str, dict[str, Any]], node_ids: list[str], binding: dict[str, Any]) -> int:
    patched = 0
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "StartNode":
            continue
        config = get_config(node)
        title = str(config.get("window_title") or "")
        if not config.get("bind_window") or not contains_any(title, WECHAT_START_KEYWORDS):
            continue

        config["window_pid"] = binding["pid"]
        config["keep_foreground"] = True
        if contains_any(title, ["微信"]):
            config["window_hwnd"] = binding["hwnd"]
            config["window_title"] = binding["title"]
        else:
            config.pop("window_hwnd", None)
        patched += 1
    return patched


def stabilize_bound_window_clicks(nodes: dict[str, dict[str, Any]], node_ids: list[str]) -> int:
    patched = 0
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "MouseClickNode":
            continue
        config = get_config(node)
        if not config.get("use_blackboard"):
            continue
        if config.get("x_float") != 0 or config.get("y_float") != 0:
            patched += 1
        config["x_float"] = 0
        config["y_float"] = 0
    return patched


def patch_single_account(tree_data: dict[str, Any]) -> int:
    nodes = tree_data.get("nodes", {})
    root_id = tree_data.get("root_node")
    wechat_starts: list[str] = []
    for node_id in reachable_enabled_ids(nodes, root_id):
        node = nodes[node_id]
        config = get_config(node)
        if node_type(node) != "StartNode":
            continue
        if not config.get("bind_window"):
            continue
        if contains_any(config.get("window_title", ""), ["微信"]):
            wechat_starts.append(node_id)

    for node_id in wechat_starts[1:]:
        disable_subtree(nodes, node_id)
    return max(0, len(wechat_starts) - 1)


def clear_start_window_handles(nodes: dict[str, dict[str, Any]], node_ids: list[str]) -> None:
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "StartNode":
            continue
        config = get_config(node)
        if config.get("bind_window") or config.get("window_title"):
            config.pop("window_hwnd", None)
            config.pop("window_pid", None)


def patch_greeting(tree_data: dict[str, Any], node_ids: list[str], greeting_text: str) -> set[str]:
    nodes = tree_data.get("nodes", {})
    greeting_ids: set[str] = set()
    safe_greeting_text = normalize_greeting_text(greeting_text)
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "TextInputNode":
            continue
        if contains_any(node_name(node), GREETING_KEYWORDS):
            greeting_ids.add(node_id)
            if safe_greeting_text:
                config = get_config(node)
                config["input_mode"] = "预设文本"
                config["preset_texts"] = [safe_greeting_text]
                config["clear_before_input"] = True
    return greeting_ids


def patch_skip_tag_flow(tree_data: dict[str, Any], node_ids: list[str], greeting_ids: set[str]) -> None:
    nodes = tree_data.get("nodes", {})
    parents = parent_map(nodes)

    confirm_parent_ids: list[str] = []
    for node_id in node_ids:
        node = nodes[node_id]
        if contains_any(node_name(node), CONFIRM_CLICK_KEYWORDS) and node_type(node) == "MouseClickNode":
            parent_id = parents.get(node_id)
            if parent_id:
                confirm_parent_ids.append(parent_id)

    if not confirm_parent_ids:
        return

    for greeting_id in greeting_ids:
        greeting = nodes.get(greeting_id)
        if not greeting:
            continue
        children = [str(child_id) for child_id in greeting.get("children", []) or []]
        if not children:
            continue
        delay_id = children[0]
        if delay_id not in nodes:
            continue

        nearest_confirm_parent = min(
            confirm_parent_ids,
            key=lambda candidate: abs(node_y(nodes[candidate]) - node_y(greeting)),
        )
        set_children(nodes, delay_id, [nearest_confirm_parent])

    tag_keywords = ["标签", "点击标签", "备注", "输入备注"]
    for node_id in node_ids:
        node = nodes[node_id]
        if contains_any(node_name(node), tag_keywords):
            set_node_enabled(node, False)


def int_config_value(config: dict[str, Any], key: str, default: int = 0) -> int:
    value = config.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def nearest_start_ancestor(
    nodes: dict[str, dict[str, Any]],
    parents: dict[str, str],
    node_id: str,
    title_keywords: list[str],
) -> str | None:
    current = parents.get(node_id)
    while current:
        node = nodes.get(current)
        if node and node_type(node) == "StartNode":
            config = get_config(node)
            if config.get("bind_window") and contains_any(config.get("window_title", ""), title_keywords):
                return current
        current = parents.get(current)
    return None


def find_search_cleanup_start(nodes: dict[str, dict[str, Any]], node_ids: list[str]) -> str | None:
    node_id_set = set(node_ids)
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "StartNode":
            continue
        config = get_config(node)
        if not config.get("bind_window") or not contains_any(config.get("window_title", ""), ["添加朋友"]):
            continue
        for child_id in node.get("children", []) or []:
            child = nodes.get(str(child_id))
            if child and str(child_id) in node_id_set and contains_any(node_name(child), SEARCH_CLEANUP_KEYWORDS):
                return node_id
    return None


def find_success_close_clicks(nodes: dict[str, dict[str, Any]], node_ids: list[str]) -> set[str]:
    parents = parent_map(nodes)
    close_ids: set[str] = set()
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "MouseClickNode":
            continue
        if not contains_any(node_name(node), CLOSE_FRIEND_WINDOW_KEYWORDS):
            continue
        if nearest_start_ancestor(nodes, parents, node_id, ["添加朋友"]):
            close_ids.add(node_id)
    return close_ids


def disable_target_input_validation(nodes: dict[str, dict[str, Any]], node_ids: list[str]) -> set[str]:
    disabled_ids: set[str] = set()
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "VariableConditionNode":
            continue
        if not contains_any(node_name(node), VALIDATION_KEYWORDS):
            continue
        set_node_enabled(node, False)
        disabled_ids.add(node_id)
    return disabled_ids


def patch_search_not_found_recovery(tree_data: dict[str, Any], node_ids: list[str]) -> set[str]:
    nodes = tree_data.get("nodes", {})
    parents = parent_map(nodes)
    active_ids = set(node_ids)
    not_found_ids: set[str] = set()
    cleanup_start_id = find_search_cleanup_start(nodes, node_ids)

    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "ImageConditionNode":
            continue
        if not contains_any(node_name(node), ADD_TO_CONTACTS_KEYWORDS):
            continue

        not_found_ids.add(node_id)
        config = get_config(node)
        if int_config_value(config, "retry_count") < SEARCH_RESULT_RETRY_COUNT:
            config["retry_count"] = SEARCH_RESULT_RETRY_COUNT
        config["repeat_interval_ms"] = SEARCH_RESULT_RETRY_INTERVAL_MS

        success_children = [str(child_id) for child_id in node.get("children", []) or [] if str(child_id) in nodes]
        if not success_children:
            continue

        node["children"] = []
        parent_id = parents.get(node_id)
        if not parent_id or parent_id not in nodes:
            continue

        parent_children = [str(child_id) for child_id in nodes[parent_id].get("children", []) or []]
        patched_children: list[str] = []
        for child_id in parent_children:
            if child_id not in nodes or child_id in patched_children:
                continue
            patched_children.append(child_id)
            if child_id == node_id:
                for success_child in success_children:
                    if success_child not in patched_children:
                        patched_children.append(success_child)
        set_children(nodes, parent_id, patched_children)

    if cleanup_start_id:
        parents = parent_map(nodes)
        cleanup_parent_id = parents.get(cleanup_start_id)
        for node_id in not_found_ids:
            search_start_id = nearest_start_ancestor(nodes, parents, node_id, ["添加朋友"])
            if not search_start_id or search_start_id == cleanup_start_id:
                continue

            if cleanup_parent_id and cleanup_parent_id in nodes and cleanup_parent_id != search_start_id:
                set_children(
                    nodes,
                    cleanup_parent_id,
                    [str(child_id) for child_id in nodes[cleanup_parent_id].get("children", []) or [] if str(child_id) != cleanup_start_id],
                )

            search_children = [str(child_id) for child_id in nodes[search_start_id].get("children", []) or []]
            if cleanup_start_id not in search_children and cleanup_start_id in active_ids:
                search_children.append(cleanup_start_id)
                set_children(nodes, search_start_id, search_children)

    return not_found_ids


def patch_tree(tree_file: Path, task_config: dict[str, Any]) -> dict[str, Any]:
    with tree_file.open("r", encoding="utf-8") as f:
        tree_data = json.load(f)

    nodes: dict[str, dict[str, Any]] = tree_data.get("nodes", {})
    slot_id = int(task_config.get("slot_id") or 1)
    binding = parse_wechat_binding(task_config)
    if not binding:
        raise RuntimeError(f"微信{slot_id}未绑定有效窗口，请先在客户端绑定微信窗口")

    disabled_accounts = patch_single_account(tree_data)
    active_ids = reachable_enabled_ids(nodes, tree_data.get("root_node"))
    if binding:
        patched_windows = apply_wechat_binding(nodes, active_ids, binding)
        if patched_windows == 0:
            raise RuntimeError("AutoDoor 项目中没有找到可绑定的微信开始节点")
        active_ids = reachable_enabled_ids(nodes, tree_data.get("root_node"))

    task_targets = parse_task_targets(task_config)
    target_type = task_targets[0].target_type if task_targets else normalize_target_type(task_config.get("target_type"))
    input_keywords = WECHAT_ID_INPUT_KEYWORDS if target_type == "wechat_id" else PHONE_INPUT_KEYWORDS
    target_input_ids = [
        node_id
        for node_id in active_ids
        if node_type(nodes[node_id]) == "TextInputNode"
        and contains_any(node_name(nodes[node_id]), input_keywords)
    ]
    if not target_input_ids and target_type == "wechat_id":
        target_input_ids = [
            node_id
            for node_id in active_ids
            if node_type(nodes[node_id]) == "TextInputNode"
            and contains_any(node_name(nodes[node_id]), PHONE_INPUT_KEYWORDS)
        ]
    if not target_input_ids:
        raise RuntimeError(f"AutoDoor 项目中没有找到{target_label(target_type)}输入节点")

    if task_targets:
        limit = max(1, min(int(task_config.get("daily_limit") or 1), len(task_targets)))
        task_targets = task_targets[:limit]
    elif target_type == "phone":
        validate_phone_pool(nodes, target_input_ids)
        phone_pool = extract_phone_pool(nodes, target_input_ids)
        if not phone_pool:
            raise RuntimeError("AutoDoor 项目中没有找到手机号输入节点或手机号池")
        limit = max(1, min(int(task_config.get("daily_limit") or 1), len(phone_pool)))
        task_targets = [
            PreparedTarget(target_id=None, target_type="phone", target_value=phone)
            for phone in phone_pool[:limit]
        ]
    else:
        raise RuntimeError("后端没有下发微信号任务数据")

    phone_numbers = [target.target_value for target in task_targets]

    for node_id in target_input_ids:
        config = get_config(nodes[node_id])
        config["input_mode"] = "预设文本"
        config["preset_texts"] = phone_numbers
        config["execution_mode"] = "顺序"
        config.pop("file_path", None)
        config["save_input_text"] = True
        config["output_key"] = "last_input_text"

    if not binding:
        clear_start_window_handles(nodes, active_ids)

    root_id = tree_data.get("root_node")
    repeat_interval_ms = 0
    repeat_interval_ms_random = 0
    if root_id in nodes:
        root_config = get_config(nodes[root_id])
        repeat_interval_ms, repeat_interval_ms_random = parse_add_interval_config(task_config)
        root_config["repeat_count"] = 0
        root_config["repeat_interval_ms"] = str(repeat_interval_ms)
        root_config["repeat_interval_ms_random"] = str(repeat_interval_ms_random)

    greeting_ids = patch_greeting(tree_data, active_ids, str(task_config.get("greeting_text") or "").strip())
    if not bool(task_config.get("create_tag")):
        patch_skip_tag_flow(tree_data, active_ids, greeting_ids)
        active_ids = reachable_enabled_ids(nodes, root_id)

    disabled_validation_ids = disable_target_input_validation(nodes, active_ids)
    if disabled_validation_ids:
        active_ids = reachable_enabled_ids(nodes, root_id)

    append_worker_log(
        "patch_tree task_runtime",
        target_type=target_type,
        target_count=len(phone_numbers),
        repeat_count=0,
        repeat_interval_ms=repeat_interval_ms,
        repeat_interval_ms_random=repeat_interval_ms_random,
        greeting_nodes=sorted(greeting_ids),
        has_greeting=bool(str(task_config.get("greeting_text") or "").strip()),
        disabled_validation_ids=sorted(disabled_validation_ids),
    )

    not_found_ids = patch_search_not_found_recovery(tree_data, active_ids)
    active_ids = reachable_enabled_ids(nodes, root_id)
    stabilized_clicks = stabilize_bound_window_clicks(nodes, active_ids)

    validation_ids = {
        node_id
        for node_id in active_ids
        if node_type(nodes[node_id]) == "VariableConditionNode"
        and contains_any(node_name(nodes[node_id]), VALIDATION_KEYWORDS)
    }
    confirm_click_ids = {
        node_id
        for node_id in active_ids
        if node_type(nodes[node_id]) == "MouseClickNode"
        and contains_any(node_name(nodes[node_id]), CONFIRM_CLICK_KEYWORDS)
    }
    success_close_ids = find_success_close_clicks(nodes, active_ids)
    key_failure_ids = {
        node_id
        for node_id in active_ids
        if contains_any(node_name(nodes[node_id]), KEY_FAILURE_KEYWORDS)
    }

    rebuild_connections(tree_data)

    surrogate_count = count_surrogate_chars(tree_data)
    if surrogate_count:
        append_worker_log("patch_tree sanitized_surrogates", count=surrogate_count)
        tree_data = sanitize_json_value(tree_data)

    with tree_file.open("w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)

    return {
        "target_type": target_type,
        "targets": task_targets,
        "phone_numbers": phone_numbers,
        "phone_input_ids": target_input_ids,
        "validation_ids": validation_ids,
        "not_found_ids": not_found_ids,
        "confirm_click_ids": confirm_click_ids,
        "success_close_ids": success_close_ids,
        "key_failure_ids": key_failure_ids,
        "disabled_validation_ids": disabled_validation_ids,
        "disabled_accounts": disabled_accounts,
        "stabilized_clicks": stabilized_clicks,
    }


def prepare_run(config: AutoDoorConfig, task_config: dict[str, Any]) -> PreparedRun:
    append_worker_log(
        "prepare_run start",
        task=task_summary(task_config),
        autodoor_source_path=config.autodoor_source_path,
        project_path=config.project_path,
    )
    source_project = Path(config.project_path)
    if not source_project.exists():
        raise RuntimeError(f"AutoDoor 项目不存在: {source_project}")
    if not (source_project / "project.json").exists() or not (source_project / "tree.json").exists():
        raise RuntimeError(f"AutoDoor 项目不完整，需要 project.json 和 tree.json: {source_project}")

    run_id = safe_run_id(task_config.get("run_id") or task_config.get("task_id"))
    run_dir = app_data_dir() / "runs" / run_id
    runs_root = app_data_dir() / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    if run_dir.exists():
        resolved_run = run_dir.resolve()
        resolved_root = runs_root.resolve()
        if resolved_root not in resolved_run.parents and resolved_run != resolved_root:
            raise RuntimeError("运行目录不在 FriendAuto runs 目录内，已拒绝清理")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    project_dir = run_dir / PROJECT_COPY_NAME
    shutil.copytree(source_project, project_dir)
    tree_file = project_dir / "tree.json"
    append_worker_log(
        "prepare_run copied_project",
        run_dir=str(run_dir),
        project_dir=str(project_dir),
        tree_file=str(tree_file),
    )

    patched = patch_tree(
        tree_file=tree_file,
        task_config=task_config,
    )
    append_worker_log(
        "prepare_run patched_tree",
        target_type=patched["target_type"],
        target_count=len(patched["targets"]),
        phone_input_ids=list(patched["phone_input_ids"]),
        validation_ids=list(patched["validation_ids"]),
        not_found_ids=list(patched["not_found_ids"]),
        confirm_click_ids=list(patched["confirm_click_ids"]),
        success_close_ids=list(patched["success_close_ids"]),
        key_failure_ids=list(patched["key_failure_ids"]),
        disabled_validation_ids=list(patched.get("disabled_validation_ids", [])),
    )

    base_tree_file = project_dir / "friendauto_base_tree.json"
    shutil.copyfile(tree_file, base_tree_file)

    return PreparedRun(
        run_dir=run_dir,
        project_dir=project_dir,
        tree_file=tree_file,
        base_tree_file=base_tree_file,
        target_type=patched["target_type"],
        targets=patched["targets"],
        phone_numbers=patched["phone_numbers"],
        phone_input_ids=set(patched["phone_input_ids"]),
        validation_ids=set(patched["validation_ids"]),
        not_found_ids=set(patched["not_found_ids"]),
        confirm_click_ids=set(patched["confirm_click_ids"]),
        success_close_ids=set(patched["success_close_ids"]),
        key_failure_ids=set(patched["key_failure_ids"]),
    )


def dependency_path_matches_python(path: Path) -> bool:
    pyd_files = list(path.rglob("*.pyd"))
    if not pyd_files:
        return True
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    return any(tag in pyd.name for pyd in pyd_files)


def add_runtime_dll_directories(paths: list[Path]) -> None:
    dll_dirs: list[Path] = []
    seen: set[str] = set()

    def add_dir(path: Path) -> None:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key not in seen and resolved.is_dir():
            seen.add(key)
            dll_dirs.append(resolved)

    for path in paths:
        add_dir(path)
        add_dir(path / "cv2")
        for pattern in ("*.dll", "*.pyd"):
            for item in path.rglob(pattern):
                add_dir(item.parent)

    if dll_dirs:
        existing_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(str(path) for path in dll_dirs) + os.pathsep + existing_path

    if hasattr(os, "add_dll_directory"):
        for path in dll_dirs:
            try:
                _dll_directory_handles.append(os.add_dll_directory(str(path)))
            except OSError as exc:
                append_worker_log("add_dll_directory failed", path=str(path), error=str(exc))

    append_worker_log("runtime_dll_directories added", count=len(dll_dirs), paths=[str(path) for path in dll_dirs[:80]])


def candidate_dependency_paths(config: AutoDoorConfig) -> list[Path]:
    paths: list[Path] = []
    source = Path(config.autodoor_source_path)
    paths.append(source / "dist" / "autodoor-behaviortree-1.6.0" / "_internal")

    if config.editor_executable_path:
        editor_path = Path(config.editor_executable_path)
        editor_dir = editor_path.parent if editor_path.is_file() else editor_path
        paths.append(editor_dir / "_internal")

    return [path for path in paths if path.exists() and dependency_path_matches_python(path)]


def candidate_python_import_paths(dependency_paths: list[Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    def add_path(path: Path) -> None:
        key = str(path).lower()
        if key not in seen and path.exists():
            seen.add(key)
            paths.append(path)

    for dependency_path in dependency_paths:
        add_path(dependency_path)
        add_path(dependency_path / "base_library.zip")
    return paths


def prepend_sys_paths(paths: list[Path]) -> None:
    ordered: list[str] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve() if path.exists() else path).lower()
        if key not in seen and path.exists():
            seen.add(key)
            ordered.append(str(path))

    for path in ordered:
        while path in sys.path:
            sys.path.remove(path)

    for path in reversed(ordered):
        sys.path.insert(0, path)


def clear_autodoor_dependency_modules() -> list[str]:
    removed: list[str] = []
    prefixes = AUTODOOR_EXTERNAL_MODULE_PREFIXES
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in prefixes):
            removed.append(module_name)
            sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return removed


def module_file(module: Any) -> str:
    value = getattr(module, "__file__", "")
    if value:
        return str(value)
    paths = getattr(module, "__path__", None)
    if paths:
        return ";".join(str(path) for path in paths)
    return "<unknown>"


def preflight_autodoor_dependencies() -> None:
    try:
        pil = importlib.import_module("PIL")
        image_grab = importlib.import_module("PIL.ImageGrab")
        image = importlib.import_module("PIL.Image")
        cv2_module = importlib.import_module("cv2")
    except Exception as exc:
        append_worker_log(
            "nuitka_dependency_preflight_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            traceback=traceback.format_exc(),
            sys_path=sys.path[:30],
        )
        raise

    append_worker_log(
        "nuitka_dependency_preflight",
        pil_file=module_file(pil),
        imagegrab_file=module_file(image_grab),
        image_file=module_file(image),
        cv2_file=module_file(cv2_module),
        sys_path=sys.path[:12],
    )


def import_autodoor(config: AutoDoorConfig):
    source = Path(config.autodoor_source_path)
    dependency_paths = candidate_dependency_paths(config)
    import_paths = candidate_python_import_paths(dependency_paths)
    append_worker_log(
        "import_autodoor start",
        source=str(source),
        source_exists=source.exists(),
        dependency_paths=[str(path) for path in dependency_paths],
        import_paths=[str(path) for path in import_paths],
        sys_executable=sys.executable,
    )
    if not source.exists():
        raise RuntimeError(f"AutoDoor 源码目录不存在: {source}")
    add_runtime_dll_directories(dependency_paths)
    prepend_sys_paths(import_paths + [source])
    removed_modules = clear_autodoor_dependency_modules()
    append_worker_log(
        "autodoor_dependency_modules_cleared",
        count=len(removed_modules),
        modules=removed_modules[:80],
    )
    preflight_autodoor_dependencies()

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from bt_utils.dpi_awareness import initialize_dpi_awareness

            initialize_dpi_awareness()

            from bt_core.context import ExecutionContext
            from bt_core.engine import BehaviorTreeEngine
            from bt_core.registry import register_all_nodes
            from bt_core.serializer import Serializer
            from bt_utils.log_manager import LogLevel, LogManager
            from bt_utils.ui_dispatcher import UIUpdateDispatcher

            register_all_nodes()
            LogManager.set_console_output(False)
    except ModuleNotFoundError as exc:
        missing = exc.name or str(exc)
        append_worker_log(
            "import_autodoor module_not_found",
            missing=missing,
            error=str(exc),
            traceback=traceback.format_exc(),
            sys_path=sys.path[:30],
        )
        raise RuntimeError(
            "AutoDoor Python 运行依赖缺失或版本不匹配: "
            f"{missing}。请为 FriendAuto 启动 worker 的 Python 安装 "
            f"{Path(config.autodoor_source_path) / 'requirements.txt'}，"
            "或使用与 AutoDoor 打包版一致的 Python 3.11 环境。"
        ) from exc
    except Exception as exc:
        append_worker_log(
            "import_autodoor failed",
            error=str(exc),
            traceback=traceback.format_exc(),
            sys_path=sys.path[:30],
        )
        raise
    append_worker_log("import_autodoor ok", source=str(source))
    return ExecutionContext, BehaviorTreeEngine, Serializer, LogManager, LogLevel, UIUpdateDispatcher


def patch_text_input_clipboard_lock() -> None:
    from bt_nodes.actions.text_input import TextInputNode

    if getattr(TextInputNode._input_text_fast, "_friendauto_clipboard_locked", False):
        return

    original_fast = TextInputNode._input_text_fast
    original_slow = TextInputNode._input_text_slow

    def ensure_text_input_allowed(context) -> None:
        run_id = getattr(context, "_friendauto_run_id", "")
        if stop_requested(run_id):
            context._is_running = False
            raise RuntimeError("任务已停止，取消本次文本输入")

    def locked_fast(self, context, text: str) -> None:
        ensure_text_input_allowed(context)
        with interprocess_file_lock(CLIPBOARD_LOCK_FILE_NAME):
            ensure_text_input_allowed(context)
            return original_fast(self, context, text)

    def locked_slow(self, context, text: str) -> None:
        ensure_text_input_allowed(context)
        with interprocess_file_lock(CLIPBOARD_LOCK_FILE_NAME):
            ensure_text_input_allowed(context)
            return original_slow(self, context, text)

    locked_fast._friendauto_clipboard_locked = True  # type: ignore[attr-defined]
    locked_slow._friendauto_clipboard_locked = True  # type: ignore[attr-defined]
    TextInputNode._input_text_fast = locked_fast
    TextInputNode._input_text_slow = locked_slow


def configure_bound_window_runtime() -> None:
    from bt_utils.input_manager import InputControllerManager

    manager = InputControllerManager()
    manager._keyboard_method = "bg"
    manager._mouse_method = "bg"
    patch_text_input_clipboard_lock()


def should_retry_bootstrap(outcome: RunOutcome, attempt: int) -> bool:
    return (
        attempt < BOOTSTRAP_MAX_ATTEMPTS
        and not outcome.phone_started
        and outcome.total_finished == 0
        and outcome.elapsed_seconds <= BOOTSTRAP_RETRY_MAX_SECONDS
    )


def random_interval_ms(base_interval_ms: int, random_range_ms: int) -> int:
    if random_range_ms <= 0:
        return max(0, int(base_interval_ms))
    lower = max(0, int(base_interval_ms) - int(random_range_ms))
    upper = max(lower, int(base_interval_ms) + int(random_range_ms))
    return random.randint(lower, upper)


def write_tree_for_single_target(prepared: PreparedRun, target: PreparedTarget) -> None:
    shutil.copyfile(prepared.base_tree_file, prepared.tree_file)
    with prepared.tree_file.open("r", encoding="utf-8") as f:
        tree_data = json.load(f)

    nodes: dict[str, dict[str, Any]] = tree_data.get("nodes", {})
    for node_id in prepared.phone_input_ids:
        node = nodes.get(node_id)
        if not node:
            continue
        config = get_config(node)
        config["input_mode"] = "预设文本"
        config["preset_texts"] = [target.target_value]
        config["execution_mode"] = "顺序"
        config.pop("file_path", None)
        config["save_input_text"] = True
        config["output_key"] = "last_input_text"

    root_id = tree_data.get("root_node")
    if root_id in nodes:
        root_config = get_config(nodes[root_id])
        root_config["repeat_count"] = 0

    with prepared.tree_file.open("w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)


def prepared_run_for_target(prepared: PreparedRun, target: PreparedTarget) -> PreparedRun:
    return PreparedRun(
        run_dir=prepared.run_dir,
        project_dir=prepared.project_dir,
        tree_file=prepared.tree_file,
        base_tree_file=prepared.base_tree_file,
        target_type=prepared.target_type,
        targets=[target],
        phone_numbers=[target.target_value],
        phone_input_ids=prepared.phone_input_ids,
        validation_ids=prepared.validation_ids,
        not_found_ids=prepared.not_found_ids,
        confirm_click_ids=prepared.confirm_click_ids,
        success_close_ids=prepared.success_close_ids,
        key_failure_ids=prepared.key_failure_ids,
    )


def close_add_friend_window(task_config: dict[str, Any], run_id: str, reason: str) -> bool:
    binding = parse_wechat_binding(task_config)
    pid = int(binding.get("pid") or 0) if binding else 0
    try:
        from bt_utils.window_manager import WindowManager

        hwnd, find_method = WindowManager.find_window_smart(
            pid if pid > 0 else None,
            "添加朋友",
        )
        if not hwnd:
            append_worker_log(
                "close_add_friend_window not_found",
                run_id=run_id,
                reason=reason,
                pid=pid,
            )
            return False

        win32gui = importlib.import_module("win32gui")
        win32con = importlib.import_module("win32con")
        ok = bool(win32gui.PostMessage(int(hwnd), win32con.WM_CLOSE, 0, 0))
        append_worker_log(
            "close_add_friend_window",
            run_id=run_id,
            reason=reason,
            hwnd=int(hwnd),
            find_method=find_method,
            pid=pid,
            ok=ok,
        )
        return ok
    except Exception as exc:
        append_worker_log(
            "close_add_friend_window error",
            run_id=run_id,
            reason=reason,
            pid=pid,
            error=repr(exc),
        )
        return False


def detect_already_friend_screen(context: Any, run_id: str) -> bool:
    try:
        screenshot = context.get_screenshot()
        if screenshot is None:
            append_worker_log("already_friend_screen_check", run_id=run_id, found=False, reason="no_screenshot")
            return False

        from bt_utils.ocr_manager import OCRManager

        keywords = ",".join(ALREADY_FRIEND_KEYWORDS)
        found, position, all_text = OCRManager().recognize(
            screenshot,
            keywords=keywords,
            language="chi_sim",
            preprocess_mode="normal",
            use_cache=False,
        )
        compact_text = re.sub(r"\s+", "", str(all_text or ""))
        fallback_found = any(keyword in compact_text for keyword in ALREADY_FRIEND_KEYWORDS)
        final_found = bool(found or fallback_found)
        append_worker_log(
            "already_friend_screen_check",
            run_id=run_id,
            found=final_found,
            ocr_found=bool(found),
            fallback_found=fallback_found,
            position=position,
            text_preview=str(all_text or "")[:220],
        )
        return final_found
    except Exception as exc:
        append_worker_log(
            "already_friend_screen_check error",
            run_id=run_id,
            found=False,
            error=repr(exc),
        )
        return False


def run_autodoor_once(
    deps: tuple[Any, Any, Any, Any, Any, Any],
    prepared: PreparedRun,
    task_config: dict[str, Any],
) -> RunOutcome:
    (
        ExecutionContext,
        BehaviorTreeEngine,
        Serializer,
        LogManager,
        LogLevel,
        UIUpdateDispatcher,
    ) = deps

    root_node, _, _ = Serializer.load_from_file(str(prepared.tree_file))
    if not root_node:
        raise RuntimeError("AutoDoor tree.json 没有有效根节点")

    run_id = str(task_config.get("run_id") or task_config.get("task_id") or "")
    raise_if_stop_requested(run_id)
    node_meta = load_node_meta(prepared.tree_file)
    dispatcher = UIUpdateDispatcher()
    log_manager = LogManager.instance()
    log_manager.flush()

    state = {
        "target_index": -1,
        "current_target": None,
        "awaiting_success_close_key": None,
        "awaiting_already_friend_close_key": None,
        "awaiting_invalid_close_key": None,
        "input_started": False,
        "last_input_text": "",
        "same_input_success_count": 0,
        "abort_current_target": False,
        "pending_invalid": {},
        "completed": set(),
        "failed": set(),
        "invalid": set(),
    }

    def current_contact_id() -> int | None:
        return target_contact_id(state["current_target"])

    def target_result_key(target: PreparedTarget | None) -> int | None:
        if not target:
            return None
        return target.target_id or target_contact_id(target)

    def terminal_result_keys() -> set[int]:
        return state["completed"] | state["failed"] | state["invalid"]

    def current_target_is_terminal() -> bool:
        result_key = target_result_key(state["current_target"])
        return result_key is not None and result_key in terminal_result_keys()

    def target_index_for_value(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        for index, target in enumerate(prepared.targets):
            if str(target.target_value or "").strip() == text:
                return index
        return None

    def current_input_text() -> str:
        try:
            return str(context.blackboard.get("last_input_text", "") or "").strip()
        except Exception:
            return ""

    def normalized_input_text(value: Any) -> str:
        return str(value or "").strip()

    def clear_pending_invalid(
        result_key: int,
        reason: str,
        event_name: str = "",
        target: PreparedTarget | None = None,
    ) -> dict[str, Any] | None:
        record = state["pending_invalid"].pop(result_key, None)
        if not record:
            return None
        append_worker_log(
            "pending_invalid_cleared",
            run_id=run_id,
            reason=reason,
            event=event_name,
            pending_reason=record.get("reason"),
            pending_message=record.get("message"),
            target_index=state["target_index"],
            target_id=target.target_id if target else None,
        )
        if event_name == "success":
            append_worker_log(
                "success_overrides_pending_invalid",
                run_id=run_id,
                pending_reason=record.get("reason"),
                pending_message=record.get("message"),
                target_index=state["target_index"],
                target_id=target.target_id if target else None,
            )
        return record

    def set_pending_invalid(message: str, reason: str, node_id: str = "") -> None:
        target = state["current_target"]
        if not target:
            return
        result_key = target_result_key(target)
        if result_key is None:
            return
        if current_target_is_terminal():
            append_worker_log(
                "pending_invalid_ignored_terminal",
                run_id=run_id,
                reason=reason,
                node_id=node_id,
                target_index=state["target_index"],
                target_id=target.target_id,
            )
            return
        state["pending_invalid"][result_key] = {
            "message": message,
            "reason": reason,
            "node_id": node_id,
        }
        append_worker_log(
            "pending_invalid_set",
            run_id=run_id,
            reason=reason,
            node_id=node_id,
            target_index=state["target_index"],
            target_id=target.target_id,
            result_message=message,
        )

    def finalize_pending_invalid(reason: str) -> bool:
        target = state["current_target"]
        if not target:
            return False
        result_key = target_result_key(target)
        if result_key is None or current_target_is_terminal():
            return False
        record = state["pending_invalid"].get(result_key)
        if not record:
            return False
        append_worker_log(
            "pending_invalid_finalized",
            run_id=run_id,
            reason=reason,
            pending_reason=record.get("reason"),
            target_index=state["target_index"],
            target_id=target.target_id,
            result_message=record.get("message"),
        )
        if reason != "search_cleanup_closed":
            close_add_friend_window(task_config, run_id, f"pending_invalid_{reason}")
        mark_terminal("invalid", str(record.get("message") or "当前联系人无效"))
        return True

    def mark_terminal(event_name: str, message: str) -> None:
        target = state["current_target"]
        if not target:
            return
        contact_id = target_contact_id(target)
        result_key = target_result_key(target)
        if result_key is None:
            return
        if result_key in state["completed"]:
            return
        if result_key in state["failed"] or result_key in state["invalid"]:
            if event_name != "success":
                return
            append_worker_log(
                "success_overrides_previous_terminal",
                run_id=run_id,
                target_index=state["target_index"],
                target_id=target.target_id,
                was_failed=result_key in state["failed"],
                was_invalid=result_key in state["invalid"],
            )
            state["failed"].discard(result_key)
            state["invalid"].discard(result_key)
        for key in ["awaiting_success_close_key", "awaiting_already_friend_close_key", "awaiting_invalid_close_key"]:
            if state.get(key) == result_key:
                state[key] = None
        clear_pending_invalid(result_key, f"terminal_{event_name}", event_name, target)
        if event_name == "success":
            state["completed"].add(result_key)
        elif event_name == "invalid":
            state["invalid"].add(result_key)
        else:
            state["failed"].add(result_key)
        emit(
            event_name,
            message,
            run_id=run_id,
            target_id=target.target_id,
            target_type=target.target_type,
            contact_id=contact_id,
        )
        append_worker_log(
            "target_terminal",
            run_id=run_id,
            event=event_name,
            target_index=state["target_index"],
            target_id=target.target_id,
            contact_id=contact_id,
            finished_count=len(terminal_result_keys()),
            total_targets=len(prepared.targets),
        )
        if state["target_index"] < len(prepared.targets) - 1:
            append_worker_log(
                "target_waiting_next_interval",
                run_id=run_id,
                current_index=state["target_index"],
                next_index=state["target_index"] + 1,
                remaining_count=max(0, len(prepared.targets) - state["target_index"] - 1),
            )

    def set_current_target(next_index: int, reason: str, input_value: str = "") -> None:
        if next_index < 0 or next_index >= len(prepared.targets):
            return
        state["target_index"] = next_index
        state["current_target"] = prepared.targets[next_index]
        state["awaiting_success_close_key"] = None
        state["awaiting_already_friend_close_key"] = None
        state["awaiting_invalid_close_key"] = None
        state["last_input_text"] = ""
        state["same_input_success_count"] = 0
        state["abort_current_target"] = False
        target = state["current_target"]
        append_worker_log(
            "target_selected",
            run_id=run_id,
            reason=reason,
            target_index=next_index,
            target_id=target.target_id,
            target_type=target.target_type,
            target_value=mask_target(target.target_type, target.target_value),
            input_value=mask_target(target.target_type, input_value) if input_value else "",
        )
        emit(
            "progress",
            f"开始处理{target_label(target.target_type)} {mask_target(target.target_type, target.target_value)}",
            run_id=run_id,
            target_id=target.target_id,
            target_type=target.target_type,
            contact_id=target_contact_id(target),
        )

    def record_target_input(input_value: str) -> None:
        text = normalized_input_text(input_value)
        if not text:
            return
        state["input_started"] = True
        if text == state["last_input_text"]:
            state["same_input_success_count"] = int(state["same_input_success_count"] or 0) + 1
        else:
            state["last_input_text"] = text
            state["same_input_success_count"] = 1

        target = state["current_target"]
        append_worker_log(
            "target_input_repeat_check",
            run_id=run_id,
            target_index=state["target_index"],
            target_id=target.target_id if target else None,
            input_value=mask_target(prepared.target_type, text),
            same_input_success_count=state["same_input_success_count"],
            abort_threshold=REPEATED_TARGET_INPUT_ABORT_COUNT,
            current_done=current_target_is_terminal(),
        )
        if (
            target
            and not current_target_is_terminal()
            and int(state["same_input_success_count"] or 0) >= REPEATED_TARGET_INPUT_ABORT_COUNT
        ):
            append_worker_log(
                "target_repeated_input_abort",
                run_id=run_id,
                target_index=state["target_index"],
                target_id=target.target_id,
                target_type=target.target_type,
                input_value=mask_target(target.target_type, text),
                same_input_success_count=state["same_input_success_count"],
            )
            close_add_friend_window(task_config, run_id, "repeated_input_abort")
            mark_terminal("failed", "当前联系人重复输入多次仍未进入下一步，跳过此联系人")
            state["abort_current_target"] = True

    def advance_current_target(input_value: str = "", reason: str = "target_input_success") -> None:
        matched_index = target_index_for_value(input_value)
        append_worker_log(
            "target_input_status",
            run_id=run_id,
            reason=reason,
            input_value=mask_target(prepared.target_type, input_value) if input_value else "",
            matched_index=matched_index,
            current_index=state["target_index"],
            current_done=current_target_is_terminal(),
            finished_count=len(terminal_result_keys()),
            total_targets=len(prepared.targets),
        )

        if state["target_index"] < 0:
            set_current_target(matched_index if matched_index is not None else 0, reason, input_value)
        record_target_input(input_value)
        if state["abort_current_target"]:
            return

        if not current_target_is_terminal():
            append_worker_log(
                "target_input_ignored_until_terminal",
                run_id=run_id,
                input_value=mask_target(prepared.target_type, input_value) if input_value else "",
                matched_index=matched_index,
                current_index=state["target_index"],
            )
            return

        next_index = state["target_index"] + 1
        if matched_index is not None and matched_index > state["target_index"]:
            next_index = matched_index
        if next_index >= len(prepared.targets):
            append_worker_log(
                "target_input_no_remaining_target",
                run_id=run_id,
                input_value=mask_target(prepared.target_type, input_value) if input_value else "",
                current_index=state["target_index"],
            )
            return
        set_current_target(next_index, reason, input_value)

    def handle_node_status(node_id: str, status: str) -> None:
        meta = node_meta.get(node_id)
        if not meta:
            return
        name = meta["name"]
        ntype = meta["type"]

        if status == "success" and node_id in prepared.phone_input_ids:
            advance_current_target(current_input_text(), "target_input_node_success")
            return

        if status == "failure" and node_id in prepared.validation_ids:
            set_pending_invalid("手机号输入校验失败", "validation_failure", node_id)
            return

        if status == "failure" and node_id in prepared.not_found_ids:
            target = state["current_target"]
            result_key = target_result_key(target)
            if result_key is not None and detect_already_friend_screen(context, run_id):
                state["awaiting_already_friend_close_key"] = result_key
                append_worker_log(
                    "already_friend_screen_detected",
                    run_id=run_id,
                    node_id=node_id,
                    target_index=state["target_index"],
                    target_id=target.target_id if target else None,
                )
                emit(
                    "progress",
                    "联系人已是好友，正在关闭添加朋友窗口",
                    run_id=run_id,
                    target_id=target.target_id if target else None,
                    target_type=target.target_type if target else None,
                    contact_id=current_contact_id(),
                )
                return
            if result_key is not None:
                state["awaiting_invalid_close_key"] = result_key
            set_pending_invalid("未找到该用户，继续处理下一条", "not_found_failure", node_id)
            return

        if status == "success" and node_id in prepared.confirm_click_ids:
            result_key = target_result_key(state["current_target"])
            if result_key is not None:
                state["awaiting_success_close_key"] = result_key
                emit(
                    "progress",
                    "好友申请已确认，正在关闭添加朋友窗口",
                    run_id=run_id,
                    target_id=state["current_target"].target_id,
                    target_type=state["current_target"].target_type,
                    contact_id=current_contact_id(),
                )
            return

        if status == "success" and node_id in prepared.success_close_ids:
            result_key = target_result_key(state["current_target"])
            if result_key is not None and state.get("awaiting_success_close_key") == result_key:
                mark_terminal("success", "好友申请已确认并关闭窗口")
                return
            if result_key is not None and state.get("awaiting_already_friend_close_key") == result_key:
                mark_terminal("success", "联系人已是好友并关闭窗口")
                return
            if result_key is not None and (
                state.get("awaiting_invalid_close_key") == result_key
                or result_key in state["pending_invalid"]
            ):
                append_worker_log(
                    "pending_invalid_close_detected",
                    run_id=run_id,
                    node_id=node_id,
                    target_index=state["target_index"],
                    target_id=state["current_target"].target_id if state["current_target"] else None,
                )
                finalize_pending_invalid("search_cleanup_closed")
                return
            append_worker_log(
                "close_click_without_terminal",
                run_id=run_id,
                node_id=node_id,
                target_index=state["target_index"],
                target_id=state["current_target"].target_id if state["current_target"] else None,
            )
            return

        if status == "failure" and node_id in prepared.key_failure_ids:
            readable_name = name or ntype
            mark_terminal("failed", f"{readable_name} 执行失败")

    def flush_logs() -> None:
        for entry in log_manager.flush():
            if entry.level == LogLevel.INFO and entry.message:
                message = str(entry.message)
                if contains_any(message, ["异常", "错误", "失败"]):
                    target = state["current_target"]
                    emit(
                        "progress",
                        message,
                        run_id=run_id,
                        target_id=target.target_id if target else None,
                        target_type=target.target_type if target else None,
                        contact_id=current_contact_id(),
                    )

    def handle_engine_status(status: str, node_status: Any = None) -> None:
        if status == "stopped":
            emit("progress", "AutoDoor 引擎已停止", run_id=run_id)

    context = ExecutionContext(project_root=str(prepared.project_dir))
    context._friendauto_run_id = run_id
    context._on_node_status = handle_node_status
    engine = BehaviorTreeEngine(root_node)
    engine._on_status_change = handle_engine_status

    start_time = time.monotonic()
    if prepared.targets:
        set_current_target(0, "target_run_start")
    engine.start(context)

    try:
        while engine.get_status().get("running"):
            if stop_requested(run_id):
                emit("progress", "收到停止指令，正在停止 AutoDoor 引擎", run_id=run_id)
                engine.stop()
                raise StopRequested()
            dispatcher.process_pending()
            flush_logs()
            if state.get("abort_current_target"):
                append_worker_log(
                    "target_abort_stop_engine",
                    run_id=run_id,
                    target_index=state["target_index"],
                    target_id=state["current_target"].target_id if state["current_target"] else None,
                )
                engine.stop()
                break
            if (
                state["current_target"]
                and not current_target_is_terminal()
                and (time.monotonic() - start_time) >= TARGET_RUN_TIMEOUT_SECONDS
            ):
                target = state["current_target"]
                append_worker_log(
                    "target_timeout_abort",
                    run_id=run_id,
                    target_index=state["target_index"],
                    target_id=target.target_id,
                    target_type=target.target_type,
                    elapsed_seconds=round(time.monotonic() - start_time, 3),
                    timeout_seconds=TARGET_RUN_TIMEOUT_SECONDS,
                    input_started=state["input_started"],
                )
                mark_terminal("failed", "当前联系人处理超时，跳过此联系人")
                engine.stop()
                break
            interruptible_sleep(0.2, run_id)
    except StopRequested:
        if engine.get_status().get("running"):
            emit("progress", "收到停止指令，正在停止 AutoDoor 引擎", run_id=run_id)
            engine.stop()
        raise
    finally:
        dispatcher.process_pending()
        flush_logs()

    result_key = target_result_key(state["current_target"])
    if (
        result_key is not None
        and not current_target_is_terminal()
        and state.get("awaiting_already_friend_close_key") == result_key
    ):
        close_add_friend_window(task_config, run_id, "already_friend_engine_finished")
        mark_terminal("success", "联系人已是好友并关闭窗口")
    else:
        finalize_pending_invalid("engine_finished")
    total_finished = len(state["completed"]) + len(state["failed"]) + len(state["invalid"])
    if state["current_target"] and total_finished == 0:
        mark_terminal("failed", "任务结束但未捕获到发送成功事件")
        total_finished = len(state["completed"]) + len(state["failed"]) + len(state["invalid"])
    pending_count = max(0, len(prepared.targets) - total_finished)
    append_worker_log(
        "run_outcome",
        run_id=run_id,
        phone_started=state["input_started"],
        total_finished=total_finished,
        success_count=len(state["completed"]),
        failed_count=len(state["failed"]),
        invalid_count=len(state["invalid"]),
        pending_count=pending_count,
        total_targets=len(prepared.targets),
        elapsed_seconds=round(time.monotonic() - start_time, 3),
    )

    return RunOutcome(
        phone_started=state["input_started"],
        total_finished=total_finished,
        success_count=len(state["completed"]),
        failed_count=len(state["failed"]),
        invalid_count=len(state["invalid"]),
        elapsed_seconds=time.monotonic() - start_time,
    )


def run_autodoor(config: AutoDoorConfig, prepared: PreparedRun, task_config: dict[str, Any]) -> None:
    deps = import_autodoor(config)
    run_id = str(task_config.get("run_id") or task_config.get("task_id") or "")
    raise_if_stop_requested(run_id)
    if parse_wechat_binding(task_config) and os.environ.get("FRIENDAUTO_FORCE_BG_INPUT") == "1":
        configure_bound_window_runtime()
        emit("progress", "已启用绑定窗口后台输入模式", run_id=run_id)

    emit(
        "started",
        f"AutoDoor 任务启动，共 {len(prepared.targets)} 个{target_label(prepared.target_type)}",
        run_id=run_id,
    )

    total_success = 0
    total_failed = 0
    total_invalid = 0
    total_finished = 0
    any_phone_started = False
    base_interval_ms, random_range_ms = parse_add_interval_config(task_config)

    for target_index, target in enumerate(prepared.targets):
        raise_if_stop_requested(run_id)
        append_worker_log(
            "target_run_begin",
            run_id=run_id,
            target_index=target_index,
            target_id=target.target_id,
            target_type=target.target_type,
            target_value=mask_target(target.target_type, target.target_value),
            total_targets=len(prepared.targets),
        )
        write_tree_for_single_target(prepared, target)
        single_prepared = prepared_run_for_target(prepared, target)

        outcome: RunOutcome | None = None
        for attempt in range(1, BOOTSTRAP_MAX_ATTEMPTS + 1):
            raise_if_stop_requested(run_id)
            if attempt > 1:
                emit("progress", f"正在重新启动第 {target_index + 1} 条任务", run_id=run_id)

            outcome = run_autodoor_once(deps, single_prepared, task_config)
            raise_if_stop_requested(run_id)
            if should_retry_bootstrap(outcome, attempt):
                emit(
                    "progress",
                    "微信窗口首次启动尚未稳定，等待后自动重试一次",
                    run_id=run_id,
                )
                interruptible_sleep(BOOTSTRAP_RETRY_DELAY_SECONDS, run_id)
                continue
            break

        if outcome is None:
            outcome = RunOutcome(False, 0, 0, 0, 0, 0)

        any_phone_started = any_phone_started or outcome.phone_started
        total_finished += outcome.total_finished
        total_success += outcome.success_count
        total_failed += outcome.failed_count
        total_invalid += outcome.invalid_count
        append_worker_log(
            "target_run_end",
            run_id=run_id,
            target_index=target_index,
            target_id=target.target_id,
            phone_started=outcome.phone_started,
            total_finished=outcome.total_finished,
            success_count=outcome.success_count,
            failed_count=outcome.failed_count,
            invalid_count=outcome.invalid_count,
            elapsed_seconds=round(outcome.elapsed_seconds, 3),
        )

        if not outcome.phone_started and outcome.total_finished == 0:
            emit(
                "error",
                f"第 {target_index + 1} 条任务未进入{target_label(prepared.target_type)}输入步骤，请确认微信已登录且“添加朋友”窗口可正常打开",
                run_id=run_id,
            )
            break

        if target_index < len(prepared.targets) - 1:
            interval_ms = random_interval_ms(base_interval_ms, random_range_ms)
            append_worker_log(
                "target_outer_wait_next_interval",
                run_id=run_id,
                current_index=target_index,
                next_index=target_index + 1,
                interval_ms=interval_ms,
                base_interval_ms=base_interval_ms,
                random_range_ms=random_range_ms,
            )
            emit(
                "progress",
                f"第 {target_index + 1} 条已结束，等待下一次加好友",
                run_id=run_id,
            )
            interruptible_sleep(interval_ms / 1000, run_id)

    pending_count = max(0, len(prepared.targets) - total_finished)
    append_worker_log(
        "run_overall_outcome",
        run_id=run_id,
        phone_started=any_phone_started,
        total_finished=total_finished,
        success_count=total_success,
        failed_count=total_failed,
        invalid_count=total_invalid,
        pending_count=pending_count,
        total_targets=len(prepared.targets),
    )

    emit(
        "finished",
        f"任务完成，成功 {total_success} 个，失败 {total_failed} 个，无效 {total_invalid} 个",
        run_id=run_id,
    )


def load_node_meta(tree_file: Path) -> dict[str, dict[str, str]]:
    with tree_file.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    nodes = raw.get("nodes", {})
    return {
        node_id: {"name": node_name(node), "type": node_type(node)}
        for node_id, node in nodes.items()
    }


def main() -> int:
    task_config: dict[str, Any] = {}
    raw = sys.stdin.read()
    append_worker_log(
        "worker main start",
        argv=sys.argv,
        executable=sys.executable,
        file=__file__,
        cwd=str(Path.cwd()),
        raw_bytes=len(raw or ""),
        runtime_base_dirs=[str(path) for path in runtime_base_dirs()],
    )
    try:
        task_config = json.loads(raw or "{}")
    except json.JSONDecodeError:
        append_worker_log("worker invalid_json", raw_preview=(raw or "")[:500])
        emit("error", "FriendAuto 传入的任务配置不是合法 JSON")
        return 1

    task_config = normalize_task_text_fields(task_config)
    task_surrogate_count = count_surrogate_chars(task_config)
    if task_surrogate_count:
        append_worker_log("worker sanitized_task_surrogates", count=task_surrogate_count)
        task_config = sanitize_json_value(task_config)

    try:
        append_worker_log("worker task_loaded", task=task_summary(task_config))
        config = load_config()
        run_id = str(task_config.get("run_id") or task_config.get("task_id") or "")
        if os.environ.get("FRIENDAUTO_IMPORT_SMOKE") == "1":
            import_autodoor(config)
            append_worker_log("worker import_smoke_ok", task=task_summary(task_config))
            emit("finished", "import smoke ok", run_id=run_id)
            return 0
        raise_if_stop_requested(run_id)
        prepared = prepare_run(config, task_config)
        raise_if_stop_requested(run_id)
        emit("progress", f"已创建运行副本: {prepared.project_dir}", run_id=run_id)
        emit("progress", "等待其他微信任务释放鼠标键盘...", run_id=run_id)
        with interprocess_file_lock(AUTOMATION_LOCK_FILE_NAME):
            raise_if_stop_requested(run_id)
            emit("progress", "已获得鼠标键盘控制权，开始执行", run_id=run_id)
            run_autodoor(config, prepared, task_config)
        return 0
    except StopRequested:
        append_worker_log("worker stop_requested", task=task_summary(task_config))
        emit("exited", "任务已停止", run_id=str(task_config.get("run_id") or task_config.get("task_id") or ""))
        return 130
    except KeyboardInterrupt:
        append_worker_log("worker keyboard_interrupt", task=task_summary(task_config))
        emit("exited", "任务已停止")
        return 130
    except Exception as exc:
        append_worker_log(
            "worker exception",
            error=str(exc),
            traceback=traceback.format_exc(),
            task=task_summary(task_config),
        )
        emit("error", str(exc), run_id=str(task_config.get("run_id") or ""))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
