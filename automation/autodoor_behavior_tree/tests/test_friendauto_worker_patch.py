import json
import importlib.util
import shutil
import sys
import tempfile
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
