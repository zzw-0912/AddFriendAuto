import json
import importlib.util
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
AUTODOOR_DIR = REPO_ROOT / "automation" / "autodoor_behavior_tree"
if str(AUTODOOR_DIR) not in sys.path:
    sys.path.insert(0, str(AUTODOOR_DIR))

import platform_worker as worker

window_manager_spec = importlib.util.spec_from_file_location(
    "friendauto_test_window_manager",
    AUTODOOR_DIR / "bt_utils" / "window_manager.py",
)
window_manager_module = importlib.util.module_from_spec(window_manager_spec)
assert window_manager_spec.loader is not None
window_manager_spec.loader.exec_module(window_manager_module)
WindowManager = window_manager_module.WindowManager


class FriendAutoWorkerPatchTest(unittest.TestCase):
    def _copy_tree(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        tree_file = Path(temp_dir.name) / "tree.json"
        shutil.copyfile(REPO_ROOT / "automation" / "Addfriend" / "tree.json", tree_file)
        return temp_dir, tree_file

    def _task_config(self) -> dict:
        return {
            "slot_id": 1,
            "target_type": "phone",
            "daily_limit": 1,
            "wechat_binding": {
                "hwnd": 123456,
                "pid": 9999,
                "title": "WeChat",
                "displayName": "WeChat",
            },
            "targets": [
                {
                    "target_id": 1,
                    "target_type": "phone",
                    "target_value": "13800138000",
                }
            ],
        }

    def _run_fake_worker_once(
        self,
        statuses: list[tuple[str, str]],
        *,
        not_found_ids: set[str] | None = None,
        close_func=None,
        already_friend_func=None,
    ):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_dir = Path(temp_dir.name)
        tree_file = project_dir / "tree.json"
        tree_file.write_text(
            json.dumps(
                {
                    "root_node": "root",
                    "nodes": {
                        "root": {"id": "root", "type": "StartNode", "name": "开始", "config": {}, "children": []},
                        "input": {"id": "input", "type": "TextInputNode", "name": "输入手机号", "config": {}, "children": []},
                        "validation": {"id": "validation", "type": "ConditionNode", "name": "判断是否输入正确", "config": {}, "children": []},
                        "not_found": {"id": "not_found", "type": "ImageConditionNode", "name": "添加到通讯录", "config": {}, "children": []},
                        "confirm": {"id": "confirm", "type": "MouseClickNode", "name": "点击确定", "config": {}, "children": []},
                        "close": {"id": "close", "type": "MouseClickNode", "name": "点击叉关闭", "config": {}, "children": []},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        prepared = worker.PreparedRun(
            run_dir=project_dir,
            project_dir=project_dir,
            tree_file=tree_file,
            base_tree_file=tree_file,
            target_type="contact",
            targets=[worker.PreparedTarget(target_id=11, target_type="contact", target_value="wxid_test")],
            phone_numbers=["wxid_test"],
            phone_input_ids={"input"},
            validation_ids={"validation"},
            not_found_ids=set(not_found_ids or []),
            confirm_click_ids={"confirm"},
            success_close_ids={"close"},
            key_failure_ids=set(),
        )

        class FakeExecutionContext:
            def __init__(self, project_root: str):
                self.project_root = project_root
                self.blackboard = {}

        class FakeEngine:
            def __init__(self, root_node):
                self.running = False

            def start(self, context):
                self.running = True
                context.blackboard["last_input_text"] = "wxid_test"
                for node_id, status in statuses:
                    context._on_node_status(node_id, status)
                self.running = False

            def get_status(self):
                return {"running": self.running}

            def stop(self):
                self.running = False

        class FakeSerializer:
            @staticmethod
            def load_from_file(path: str):
                return object(), None, None

        class FakeLogManager:
            @staticmethod
            def instance():
                return FakeLogManager()

            def flush(self):
                return []

        class FakeLogLevel:
            INFO = "INFO"

        class FakeDispatcher:
            def process_pending(self):
                return None

        emitted = []
        logs = []
        original_emit = worker.emit
        original_append_worker_log = worker.append_worker_log
        original_close_add_friend_window = worker.close_add_friend_window
        original_detect_already_friend_screen = worker.detect_already_friend_screen
        worker.emit = lambda event, message="", **extra: emitted.append({"event": event, "message": message, **extra})
        worker.append_worker_log = lambda message, **extra: logs.append({"message": message, **extra})
        worker.close_add_friend_window = close_func or (lambda *args, **kwargs: False)
        worker.detect_already_friend_screen = already_friend_func or (lambda *args, **kwargs: False)
        try:
            outcome = worker.run_autodoor_once(
                (FakeExecutionContext, FakeEngine, FakeSerializer, FakeLogManager, FakeLogLevel, FakeDispatcher),
                prepared,
                {"run_id": "fake-run"},
            )
        finally:
            worker.emit = original_emit
            worker.append_worker_log = original_append_worker_log
            worker.close_add_friend_window = original_close_add_friend_window
            worker.detect_already_friend_screen = original_detect_already_friend_screen
        return outcome, emitted, logs

    def test_patch_keeps_wechat_foreground_and_stabilizes_blackboard_clicks(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        patched = worker.patch_tree(tree_file, self._task_config())

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        nodes = tree_data["nodes"]
        active_ids = worker.reachable_enabled_ids(nodes, tree_data.get("root_node"))
        wechat_start_ids = [
            node_id
            for node_id in active_ids
            if worker.node_type(nodes[node_id]) == "StartNode"
            and worker.get_config(nodes[node_id]).get("bind_window")
            and worker.contains_any(worker.get_config(nodes[node_id]).get("window_title", ""), ["WeChat", "寰俊"])
        ]
        blackboard_click_ids = [
            node_id
            for node_id in active_ids
            if worker.node_type(nodes[node_id]) == "MouseClickNode"
            and worker.get_config(nodes[node_id]).get("use_blackboard")
        ]

        self.assertGreater(len(wechat_start_ids), 0)
        self.assertGreater(len(blackboard_click_ids), 0)
        self.assertGreater(patched["stabilized_clicks"], 0)

        for node_id in wechat_start_ids:
            config = worker.get_config(nodes[node_id])
            self.assertTrue(config.get("keep_foreground"), node_id)
            self.assertEqual(config.get("window_pid"), 9999)

        for node_id in blackboard_click_ids:
            config = worker.get_config(nodes[node_id])
            self.assertEqual(config.get("x_float"), 0, node_id)
            self.assertEqual(config.get("y_float"), 0, node_id)

    def test_account_age_profile_sets_random_repeat_interval(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        task_config = self._task_config()
        task_config["account_age_profile"] = "old"
        worker.patch_tree(tree_file, task_config)

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        root_config = worker.get_config(tree_data["nodes"][tree_data["root_node"]])
        self.assertEqual(root_config.get("repeat_count"), 0)
        self.assertEqual(root_config.get("repeat_interval_ms"), str(450 * 1000))
        self.assertEqual(root_config.get("repeat_interval_ms_random"), str(150 * 1000))

    def test_multi_target_runs_are_materialized_one_target_at_a_time(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        task_config = self._task_config()
        task_config["daily_limit"] = 2
        task_config["targets"] = [
            {"target_id": 1, "target_type": "phone", "target_value": "13800138000"},
            {"target_id": 2, "target_type": "phone", "target_value": "13900139000"},
        ]
        patched = worker.patch_tree(tree_file, task_config)
        base_tree_file = Path(temp_dir.name) / "base_tree.json"
        shutil.copyfile(tree_file, base_tree_file)
        prepared = worker.PreparedRun(
            run_dir=Path(temp_dir.name),
            project_dir=Path(temp_dir.name),
            tree_file=tree_file,
            base_tree_file=base_tree_file,
            target_type=patched["target_type"],
            targets=patched["targets"],
            phone_numbers=patched["phone_numbers"],
            phone_input_ids=patched["phone_input_ids"],
            validation_ids=patched["validation_ids"],
            not_found_ids=patched["not_found_ids"],
            confirm_click_ids=patched["confirm_click_ids"],
            success_close_ids=patched["success_close_ids"],
            key_failure_ids=patched["key_failure_ids"],
        )

        worker.write_tree_for_single_target(prepared, patched["targets"][1])

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        root_config = worker.get_config(tree_data["nodes"][tree_data["root_node"]])
        self.assertEqual(root_config.get("repeat_count"), 0)
        for node_id in patched["phone_input_ids"]:
            config = worker.get_config(tree_data["nodes"][node_id])
            self.assertEqual(config.get("preset_texts"), ["13900139000"])

    def test_wait_with_legal_probes_runs_during_existing_interval(self):
        calls = []
        logs = []
        original_probe = worker.legal_probe_request
        original_log = worker.append_worker_log
        original_interval = worker.LEGAL_PROBE_INTERVAL_SECONDS
        original_min_remaining = worker.LEGAL_PROBE_MIN_REMAINING_SECONDS

        def fake_probe(url, **kwargs):
            calls.append((url, kwargs))
            time.sleep(0.002)

        worker.legal_probe_request = fake_probe
        worker.append_worker_log = lambda message, **extra: logs.append({"message": message, **extra})
        worker.LEGAL_PROBE_INTERVAL_SECONDS = 0.03
        worker.LEGAL_PROBE_MIN_REMAINING_SECONDS = 0.005
        try:
            started = time.monotonic()
            worker.wait_with_legal_probes(0.08, "", 101, 0)
            elapsed = time.monotonic() - started
        finally:
            worker.legal_probe_request = original_probe
            worker.append_worker_log = original_log
            worker.LEGAL_PROBE_INTERVAL_SECONDS = original_interval
            worker.LEGAL_PROBE_MIN_REMAINING_SECONDS = original_min_remaining

        self.assertGreaterEqual(len(calls), 2)
        self.assertLess(elapsed, 0.35)
        self.assertTrue(any(log["message"] == "legal_probe_start" for log in logs))
        self.assertTrue(any(log["message"] == "legal_probe_finished" for log in logs))

    def test_patch_marks_missing_search_result_invalid_and_recovers_search_box(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        patched = worker.patch_tree(tree_file, self._task_config())

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        nodes = tree_data["nodes"]
        parents = worker.parent_map(nodes)
        not_found_ids = set(patched["not_found_ids"])
        self.assertGreater(len(not_found_ids), 0)

        for node_id in not_found_ids:
            node = nodes[node_id]
            config = worker.get_config(node)
            self.assertEqual(worker.node_type(node), "ImageConditionNode")
            self.assertTrue(worker.contains_any(worker.node_name(node), worker.ADD_TO_CONTACTS_KEYWORDS))
            self.assertEqual(node.get("children"), [])
            self.assertEqual(config.get("retry_count"), worker.SEARCH_RESULT_RETRY_COUNT)
            self.assertEqual(config.get("repeat_interval_ms"), worker.SEARCH_RESULT_RETRY_INTERVAL_MS)

            parent_id = parents[node_id]
            parent_children = [str(child_id) for child_id in nodes[parent_id].get("children", [])]
            self.assertIn(node_id, parent_children)
            self.assertLess(parent_children.index(node_id), len(parent_children) - 1)

        cleanup_start_ids = [
            node_id
            for node_id, node in nodes.items()
            if worker.node_type(node) == "StartNode"
            and any(
                child_id in nodes and worker.contains_any(worker.node_name(nodes[child_id]), worker.SEARCH_CLEANUP_KEYWORDS)
                for child_id in node.get("children", []) or []
            )
        ]
        self.assertGreater(len(cleanup_start_ids), 0)

        add_friend_start_ids = [
            node_id
            for node_id, node in nodes.items()
            if worker.node_type(node) == "StartNode"
            and worker.contains_any(worker.get_config(node).get("window_title", ""), ["添加朋友"])
            and any(str(child_id) in cleanup_start_ids for child_id in node.get("children", []) or [])
        ]
        self.assertGreater(len(add_friend_start_ids), 0)

    def test_patch_disables_brittle_input_validation_to_allow_search(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        patched = worker.patch_tree(tree_file, self._task_config())

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        nodes = tree_data["nodes"]
        validation_nodes = [
            node_id
            for node_id, node in nodes.items()
            if worker.node_type(node) == "VariableConditionNode"
            and worker.contains_any(worker.node_name(node), worker.VALIDATION_KEYWORDS)
        ]
        self.assertGreater(len(validation_nodes), 0)
        self.assertEqual(set(patched["validation_ids"]), set())
        self.assertGreater(len(patched["disabled_validation_ids"]), 0)
        for node_id in validation_nodes:
            self.assertFalse(worker.is_node_enabled(nodes[node_id]), node_id)

    def test_success_is_reported_after_closing_add_friend_window(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        patched = worker.patch_tree(tree_file, self._task_config())

        with tree_file.open("r", encoding="utf-8") as f:
            tree_data = json.load(f)

        nodes = tree_data["nodes"]
        parents = worker.parent_map(nodes)
        confirm_click_ids = set(patched["confirm_click_ids"])
        success_close_ids = set(patched["success_close_ids"])
        self.assertGreater(len(confirm_click_ids), 0)
        self.assertGreater(len(success_close_ids), 0)
        self.assertTrue(confirm_click_ids.isdisjoint(success_close_ids))

        for node_id in confirm_click_ids:
            node = nodes[node_id]
            self.assertEqual(worker.node_type(node), "MouseClickNode")
            self.assertTrue(worker.contains_any(worker.node_name(node), worker.CONFIRM_CLICK_KEYWORDS))

        for node_id in success_close_ids:
            node = nodes[node_id]
            self.assertEqual(worker.node_type(node), "MouseClickNode")
            self.assertTrue(worker.contains_any(worker.node_name(node), worker.CLOSE_FRIEND_WINDOW_KEYWORDS))
            self.assertIsNotNone(worker.nearest_start_ancestor(nodes, parents, node_id, ["添加朋友"]))

    def test_pending_invalid_is_overridden_by_confirmed_success(self):
        outcome, emitted, logs = self._run_fake_worker_once(
            [
                ("input", "success"),
                ("validation", "failure"),
                ("confirm", "success"),
                ("close", "success"),
            ]
        )

        result_events = [event["event"] for event in emitted if event["event"] in {"success", "invalid", "failed"}]
        self.assertEqual(result_events, ["success"])
        self.assertEqual(outcome.success_count, 1)
        self.assertEqual(outcome.invalid_count, 0)
        self.assertTrue(any(log["message"] == "pending_invalid_set" for log in logs))
        self.assertTrue(any(log["message"] == "success_overrides_pending_invalid" for log in logs))

    def test_pending_invalid_is_finalized_without_success(self):
        outcome, emitted, logs = self._run_fake_worker_once(
            [
                ("input", "success"),
                ("validation", "failure"),
            ]
        )

        result_events = [event["event"] for event in emitted if event["event"] in {"success", "invalid", "failed"}]
        self.assertEqual(result_events, ["invalid"])
        self.assertEqual(outcome.success_count, 0)
        self.assertEqual(outcome.invalid_count, 1)
        self.assertTrue(any(log["message"] == "pending_invalid_finalized" for log in logs))

    def test_repeated_input_abort_closes_add_friend_window_and_marks_failed(self):
        close_calls = []

        outcome, emitted, logs = self._run_fake_worker_once(
            [
                ("input", "success"),
                ("input", "success"),
                ("input", "success"),
                ("input", "success"),
            ],
            close_func=lambda task_config, run_id, reason: close_calls.append(reason) or True,
        )

        result_events = [event["event"] for event in emitted if event["event"] in {"success", "invalid", "failed"}]
        self.assertEqual(result_events, ["failed"])
        self.assertEqual(outcome.failed_count, 1)
        self.assertIn("repeated_input_abort", close_calls)
        self.assertTrue(any(log["message"] == "target_repeated_input_abort" for log in logs))

    def test_already_friend_screen_is_success_after_close(self):
        outcome, emitted, logs = self._run_fake_worker_once(
            [
                ("input", "success"),
                ("not_found", "failure"),
                ("close", "success"),
            ],
            not_found_ids={"not_found"},
            already_friend_func=lambda *args, **kwargs: True,
        )

        result_events = [event["event"] for event in emitted if event["event"] in {"success", "invalid", "failed"}]
        self.assertEqual(result_events, ["success"])
        self.assertEqual(outcome.success_count, 1)
        self.assertEqual(outcome.invalid_count, 0)
        self.assertTrue(any(log["message"] == "already_friend_screen_detected" for log in logs))

    def test_not_found_is_invalid_after_cleanup_close(self):
        outcome, emitted, logs = self._run_fake_worker_once(
            [
                ("input", "success"),
                ("not_found", "failure"),
                ("close", "success"),
            ],
            not_found_ids={"not_found"},
            already_friend_func=lambda *args, **kwargs: False,
        )

        result_events = [event["event"] for event in emitted if event["event"] in {"success", "invalid", "failed"}]
        self.assertEqual(result_events, ["invalid"])
        self.assertEqual(outcome.invalid_count, 1)
        self.assertTrue(any(log["message"] == "pending_invalid_close_detected" for log in logs))

    def test_patch_requires_bound_wechat_window(self):
        temp_dir, tree_file = self._copy_tree()
        self.addCleanup(temp_dir.cleanup)

        task_config = self._task_config()
        task_config.pop("wechat_binding")

        with self.assertRaises(RuntimeError):
            worker.patch_tree(tree_file, task_config)

    def test_window_title_matching_keeps_transient_wechat_titles_distinct(self):
        self.assertTrue(WindowManager._title_matches("添加朋友", "添加朋友"))
        self.assertTrue(WindowManager._title_matches("申请添加朋友", "申请添加朋友"))
        self.assertFalse(WindowManager._title_matches("申请添加朋友", "添加朋友"))


if __name__ == "__main__":
    unittest.main()
