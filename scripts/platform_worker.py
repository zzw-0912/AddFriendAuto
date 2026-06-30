"""
FriendAuto AutoDoor worker.

Reads a task JSON from stdin, prepares a per-run copy of an AutoDoor project,
patches runtime options into the copied behavior tree, runs it through the
AutoDoor source engine, and prints FriendAuto ScriptEvent JSON lines to stdout.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import threading
import time
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_AUTODOOR_SOURCE_PATH = r"D:\AddFriend\autodoor_behavior_tree"
DEFAULT_PROJECT_PATH = r"D:\AddFriend\Addfriend"
CONFIG_FILE_NAME = "autodoor.json"
PROJECT_COPY_NAME = "Addfriend"
PHONE_INPUT_KEYWORDS = ["输入手机号", "手机号"]
GREETING_KEYWORDS = ["输入申请语", "申请语"]
VALIDATION_KEYWORDS = ["判断是否输入正确", "输入正确"]
CONFIRM_CLICK_KEYWORDS = ["点击确定", "确定"]
KEY_FAILURE_KEYWORDS = ["发送添加好友申请", "添加到通讯录", "输入申请语"]
WECHAT_START_KEYWORDS = ["微信", "添加朋友", "申请添加朋友"]
BOOTSTRAP_MAX_ATTEMPTS = 2
BOOTSTRAP_RETRY_MAX_SECONDS = 8.0
BOOTSTRAP_RETRY_DELAY_SECONDS = 2.0
AUTOMATION_LOCK_FILE_NAME = "automation.lock"
CLIPBOARD_LOCK_FILE_NAME = "clipboard.lock"


@dataclass
class RunOutcome:
    phone_started: bool
    total_finished: int
    success_count: int
    failed_count: int
    invalid_count: int
    elapsed_seconds: float


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
    phone_numbers: list[str]
    phone_input_ids: set[str]
    validation_ids: set[str]
    confirm_click_ids: set[str]
    key_failure_ids: set[str]


_emit_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def emit(event: str, message: str = "", **extra: Any) -> None:
    payload = {
        "event": event,
        "message": message,
        "timestamp": now_iso(),
    }
    payload.update({key: value for key, value in extra.items() if value is not None})
    with _emit_lock:
        print(json.dumps(payload, ensure_ascii=False), flush=True)


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
    config = AutoDoorConfig(
        autodoor_source_path=DEFAULT_AUTODOOR_SOURCE_PATH,
        project_path=DEFAULT_PROJECT_PATH,
    )
    path = app_data_dir() / CONFIG_FILE_NAME
    if not path.exists():
        return config

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

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
        or ""
    ).strip()
    return config


def safe_run_id(value: Any) -> str:
    text = str(value or "manual").strip()
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
    return text[:80] or "manual"


def contact_id_for(phone: str) -> int:
    normalized = re.sub(r"\D+", "", phone)
    return zlib.crc32(normalized.encode("utf-8")) & 0x7FFFFFFF


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone)
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return phone


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
        if contains_any(title, ["微信"]):
            config["window_hwnd"] = binding["hwnd"]
            config["window_title"] = binding["title"]
        else:
            config.pop("window_hwnd", None)
        patched += 1
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
    for node_id in node_ids:
        node = nodes[node_id]
        if node_type(node) != "TextInputNode":
            continue
        if contains_any(node_name(node), GREETING_KEYWORDS):
            greeting_ids.add(node_id)
            if greeting_text:
                config = get_config(node)
                config["input_mode"] = "预设文本"
                config["preset_texts"] = [greeting_text]
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


def patch_tree(tree_file: Path, task_config: dict[str, Any]) -> dict[str, Any]:
    with tree_file.open("r", encoding="utf-8") as f:
        tree_data = json.load(f)

    nodes: dict[str, dict[str, Any]] = tree_data.get("nodes", {})
    slot_id = int(task_config.get("slot_id") or 1)
    binding = parse_wechat_binding(task_config)
    if slot_id > 1 and not binding:
        raise RuntimeError(f"微信{slot_id}未绑定有效窗口，请先在客户端绑定微信窗口")

    disabled_accounts = patch_single_account(tree_data)
    active_ids = reachable_enabled_ids(nodes, tree_data.get("root_node"))
    if binding:
        patched_windows = apply_wechat_binding(nodes, active_ids, binding)
        if patched_windows == 0:
            raise RuntimeError("AutoDoor 项目中没有找到可绑定的微信开始节点")
        active_ids = reachable_enabled_ids(nodes, tree_data.get("root_node"))

    phone_input_ids = [
        node_id
        for node_id in active_ids
        if node_type(nodes[node_id]) == "TextInputNode"
        and contains_any(node_name(nodes[node_id]), PHONE_INPUT_KEYWORDS)
    ]
    validate_phone_pool(nodes, phone_input_ids)
    phone_pool = extract_phone_pool(nodes, phone_input_ids)
    if not phone_pool:
        raise RuntimeError("AutoDoor 项目中没有找到手机号输入节点或手机号池")

    limit = max(1, min(int(task_config.get("daily_limit") or 1), len(phone_pool)))
    phone_numbers = phone_pool[:limit]

    for node_id in phone_input_ids:
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
    if root_id in nodes:
        root_config = get_config(nodes[root_id])
        root_config["repeat_count"] = max(0, len(phone_numbers) - 1)
        root_config.setdefault("repeat_interval_ms", "2000")

    greeting_ids = patch_greeting(tree_data, active_ids, str(task_config.get("greeting_text") or "").strip())
    if not bool(task_config.get("create_tag")):
        patch_skip_tag_flow(tree_data, active_ids, greeting_ids)
        active_ids = reachable_enabled_ids(nodes, root_id)

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
    key_failure_ids = {
        node_id
        for node_id in active_ids
        if contains_any(node_name(nodes[node_id]), KEY_FAILURE_KEYWORDS)
    }

    rebuild_connections(tree_data)

    with tree_file.open("w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)

    return {
        "phone_numbers": phone_numbers,
        "phone_input_ids": phone_input_ids,
        "validation_ids": validation_ids,
        "confirm_click_ids": confirm_click_ids,
        "key_failure_ids": key_failure_ids,
        "disabled_accounts": disabled_accounts,
    }


def prepare_run(config: AutoDoorConfig, task_config: dict[str, Any]) -> PreparedRun:
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

    patched = patch_tree(
        tree_file=tree_file,
        task_config=task_config,
    )

    return PreparedRun(
        run_dir=run_dir,
        project_dir=project_dir,
        tree_file=tree_file,
        phone_numbers=patched["phone_numbers"],
        phone_input_ids=set(patched["phone_input_ids"]),
        validation_ids=set(patched["validation_ids"]),
        confirm_click_ids=set(patched["confirm_click_ids"]),
        key_failure_ids=set(patched["key_failure_ids"]),
    )


def dependency_path_matches_python(path: Path) -> bool:
    pyd_files = list(path.rglob("*.pyd"))
    if not pyd_files:
        return True
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    return any(tag in pyd.name for pyd in pyd_files)


def candidate_dependency_paths(config: AutoDoorConfig) -> list[Path]:
    paths: list[Path] = []
    source = Path(config.autodoor_source_path)
    paths.append(source / "dist" / "autodoor-behaviortree-1.6.0" / "_internal")

    if config.editor_executable_path:
        editor_path = Path(config.editor_executable_path)
        editor_dir = editor_path.parent if editor_path.is_file() else editor_path
        paths.append(editor_dir / "_internal")

    return [path for path in paths if path.exists() and dependency_path_matches_python(path)]


def import_autodoor(config: AutoDoorConfig):
    source = Path(config.autodoor_source_path)
    if not source.exists():
        raise RuntimeError(f"AutoDoor 源码目录不存在: {source}")
    sys.path.insert(0, str(source))
    for dependency_path in reversed(candidate_dependency_paths(config)):
        sys.path.insert(1, str(dependency_path))

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
        raise RuntimeError(
            "AutoDoor Python 运行依赖缺失或版本不匹配: "
            f"{missing}。请为 FriendAuto 启动 worker 的 Python 安装 "
            f"{Path(config.autodoor_source_path) / 'requirements.txt'}，"
            "或使用与 AutoDoor 打包版一致的 Python 3.11 环境。"
        ) from exc
    return ExecutionContext, BehaviorTreeEngine, Serializer, LogManager, LogLevel, UIUpdateDispatcher


def patch_text_input_clipboard_lock() -> None:
    from bt_nodes.actions.text_input import TextInputNode

    if getattr(TextInputNode._input_text_fast, "_friendauto_clipboard_locked", False):
        return

    original_fast = TextInputNode._input_text_fast
    original_slow = TextInputNode._input_text_slow

    def locked_fast(self, context, text: str) -> None:
        with interprocess_file_lock(CLIPBOARD_LOCK_FILE_NAME):
            return original_fast(self, context, text)

    def locked_slow(self, context, text: str) -> None:
        with interprocess_file_lock(CLIPBOARD_LOCK_FILE_NAME):
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
    node_meta = load_node_meta(prepared.tree_file)
    dispatcher = UIUpdateDispatcher()
    log_manager = LogManager.instance()
    log_manager.flush()

    state = {
        "phone_index": -1,
        "current_phone": None,
        "completed": set(),
        "failed": set(),
        "invalid": set(),
    }

    def current_contact_id() -> int | None:
        phone = state["current_phone"]
        return contact_id_for(phone) if phone else None

    def mark_terminal(event_name: str, message: str) -> None:
        phone = state["current_phone"]
        if not phone:
            return
        contact_id = contact_id_for(phone)
        if contact_id in state["completed"] or contact_id in state["failed"] or contact_id in state["invalid"]:
            return
        if event_name == "success":
            state["completed"].add(contact_id)
        elif event_name == "invalid":
            state["invalid"].add(contact_id)
        else:
            state["failed"].add(contact_id)
        emit(event_name, message, run_id=run_id, contact_id=contact_id)

    def advance_current_phone() -> None:
        next_index = min(state["phone_index"] + 1, len(prepared.phone_numbers) - 1)
        if next_index < 0 or next_index == state["phone_index"]:
            return
        state["phone_index"] = next_index
        state["current_phone"] = prepared.phone_numbers[next_index]
        phone = state["current_phone"]
        emit(
            "progress",
            f"开始处理手机号 {mask_phone(phone)}",
            run_id=run_id,
            contact_id=contact_id_for(phone),
        )

    def handle_node_status(node_id: str, status: str) -> None:
        meta = node_meta.get(node_id)
        if not meta:
            return
        name = meta["name"]
        ntype = meta["type"]

        if status == "failure" and node_id in prepared.validation_ids:
            mark_terminal("invalid", "手机号输入校验失败")
            return

        if status == "success" and node_id in prepared.confirm_click_ids:
            mark_terminal("success", "好友申请已发送")
            return

        if status == "failure" and node_id in prepared.key_failure_ids:
            readable_name = name or ntype
            mark_terminal("failed", f"{readable_name} 执行失败")

    def flush_logs() -> None:
        for entry in log_manager.flush():
            if entry.level == LogLevel.SUCCESS and contains_any(entry.node_name, ["输入手机号", "手机号"]):
                advance_current_phone()
                continue
            if entry.level == LogLevel.INFO and entry.message:
                message = str(entry.message)
                if contains_any(message, ["异常", "错误", "失败"]):
                    emit("progress", message, run_id=run_id, contact_id=current_contact_id())

    def handle_engine_status(status: str, node_status: Any = None) -> None:
        if status == "stopped":
            emit("progress", "AutoDoor 引擎已停止", run_id=run_id)

    context = ExecutionContext(project_root=str(prepared.project_dir))
    context._on_node_status = handle_node_status
    engine = BehaviorTreeEngine(root_node)
    engine._on_status_change = handle_engine_status

    start_time = time.monotonic()
    engine.start(context)

    try:
        while engine.get_status().get("running"):
            dispatcher.process_pending()
            flush_logs()
            time.sleep(0.2)
    finally:
        dispatcher.process_pending()
        flush_logs()

    total_finished = len(state["completed"]) + len(state["failed"]) + len(state["invalid"])
    if state["current_phone"] and total_finished == 0:
        mark_terminal("failed", "任务结束但未捕获到发送成功事件")
        total_finished = len(state["completed"]) + len(state["failed"]) + len(state["invalid"])

    return RunOutcome(
        phone_started=state["phone_index"] >= 0,
        total_finished=total_finished,
        success_count=len(state["completed"]),
        failed_count=len(state["failed"]),
        invalid_count=len(state["invalid"]),
        elapsed_seconds=time.monotonic() - start_time,
    )


def run_autodoor(config: AutoDoorConfig, prepared: PreparedRun, task_config: dict[str, Any]) -> None:
    deps = import_autodoor(config)
    run_id = str(task_config.get("run_id") or task_config.get("task_id") or "")
    if parse_wechat_binding(task_config) and os.environ.get("FRIENDAUTO_FORCE_BG_INPUT") == "1":
        configure_bound_window_runtime()
        emit("progress", "已启用绑定窗口后台输入模式", run_id=run_id)

    emit(
        "started",
        f"AutoDoor 任务启动，共 {len(prepared.phone_numbers)} 个手机号",
        run_id=run_id,
    )

    outcome: RunOutcome | None = None
    for attempt in range(1, BOOTSTRAP_MAX_ATTEMPTS + 1):
        if attempt > 1:
            emit("progress", f"正在进行第 {attempt} 次启动尝试", run_id=run_id)

        outcome = run_autodoor_once(deps, prepared, task_config)
        if should_retry_bootstrap(outcome, attempt):
            emit(
                "progress",
                "微信窗口首次启动尚未稳定，等待后自动重试一次",
                run_id=run_id,
            )
            time.sleep(BOOTSTRAP_RETRY_DELAY_SECONDS)
            continue
        break

    if outcome is None:
        outcome = RunOutcome(False, 0, 0, 0, 0, 0)

    if not outcome.phone_started and outcome.total_finished == 0:
        emit(
            "error",
            "任务未进入手机号输入步骤，请确认微信已登录且“添加朋友”窗口可正常打开",
            run_id=run_id,
        )

    emit(
        "finished",
        f"任务完成，成功 {outcome.success_count} 个，失败 {outcome.failed_count} 个，无效 {outcome.invalid_count} 个",
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
    raw = sys.stdin.read()
    try:
        task_config = json.loads(raw or "{}")
    except json.JSONDecodeError:
        emit("error", "FriendAuto 传入的任务配置不是合法 JSON")
        return 1

    try:
        config = load_config()
        prepared = prepare_run(config, task_config)
        run_id = str(task_config.get("run_id") or "")
        emit("progress", f"已创建运行副本: {prepared.project_dir}", run_id=run_id)
        emit("progress", "等待其他微信任务释放鼠标键盘...", run_id=run_id)
        with interprocess_file_lock(AUTOMATION_LOCK_FILE_NAME):
            emit("progress", "已获得鼠标键盘控制权，开始执行", run_id=run_id)
            run_autodoor(config, prepared, task_config)
        return 0
    except KeyboardInterrupt:
        emit("exited", "任务已停止")
        return 130
    except Exception as exc:
        emit("error", str(exc), run_id=str(task_config.get("run_id") or ""))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
