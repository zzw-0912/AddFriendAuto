import unittest
import threading
import time
from unittest.mock import MagicMock, patch
from bt_core.engine import BehaviorTreeEngine
from bt_core.context import ExecutionContext
from bt_core.blackboard import Blackboard
from bt_core.nodes import ActionNode, NodeStatus, SequenceNode
from bt_core.config import NodeConfig
from bt_core.tree_instance import TreeInstance
from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
from bt_utils.log_manager import LogManager, LogLevel, LogEntry


class DummyAction(ActionNode):
    NODE_TYPE = "DummyAction"

    def __init__(self, node_id=None, config=None):
        super().__init__(node_id, config)
        self._tick_count = 0

    def _execute_action(self, context):
        self._tick_count += 1
        if self._tick_count >= 3:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


class AlwaysFailAction(ActionNode):
    NODE_TYPE = "AlwaysFailAction"

    def _execute_action(self, context):
        return NodeStatus.FAILURE


class TestTabIdCounter(unittest.TestCase):
    def test_tab_id_unique_after_close_reopen(self):
        manager = GuiTabManager()
        for i in range(5):
            engine = BehaviorTreeEngine(None)
            context = ExecutionContext()
            instance = TreeInstance(
                name=f"test_{i}",
                engine=engine,
                context=context,
                blackboard=Blackboard()
            )
            tab_id = f"tab_{i + 1}"
            manager.add_tab(tab_id, instance)

        manager.remove_tab("tab_2")
        instance = TreeInstance(
            name="new_tab_2",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        manager.add_tab("tab_2", instance)
        self.assertEqual(manager.get_tab("tab_2").name, "new_tab_2")

        with self.assertRaises(ValueError):
            manager.add_tab("tab_1", instance)

    def test_add_tab_duplicate_id_raises(self):
        manager = GuiTabManager()
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        manager.add_tab("tab_1", instance)
        with self.assertRaises(ValueError):
            manager.add_tab("tab_1", instance)


class TestScriptNodeExecutorIsolation(unittest.TestCase):
    def test_script_node_instance_level_executor(self):
        from bt_nodes.actions.script import ScriptNode
        node = ScriptNode(node_id="test_script", config=NodeConfig())
        self.assertIsNone(node._executor)

    def test_stop_executor_no_running_executor(self):
        from bt_nodes.actions.script import ScriptNode
        node = ScriptNode(node_id="test_script", config=NodeConfig())
        node.stop_executor()
        self.assertIsNone(node._executor)

    def test_clear_executor_pool_is_noop(self):
        from bt_nodes.actions.script import ScriptNode
        ScriptNode.clear_executor_pool()
        ScriptNode.cleanup_executor_pool()


class TestEngineStopScriptNodes(unittest.TestCase):
    def test_stop_with_no_root_node(self):
        engine = BehaviorTreeEngine(None)
        engine.stop()

    def test_stop_iterates_all_nodes(self):
        root = SequenceNode(node_id="root", config=NodeConfig())
        child1 = DummyAction(node_id="child1", config=NodeConfig())
        child2 = DummyAction(node_id="child2", config=NodeConfig())
        root.add_child(child1)
        root.add_child(child2)

        engine = BehaviorTreeEngine(root)
        context = ExecutionContext()
        engine.start(context)
        time.sleep(0.1)
        engine.stop()

    def test_iter_all_nodes(self):
        root = SequenceNode(node_id="root", config=NodeConfig())
        child1 = DummyAction(node_id="child1", config=NodeConfig())
        child2 = DummyAction(node_id="child2", config=NodeConfig())
        root.add_child(child1)
        root.add_child(child2)

        engine = BehaviorTreeEngine(root)
        nodes = list(engine._iter_all_nodes(root))
        node_ids = [n.node_id for n in nodes]
        self.assertIn("root", node_ids)
        self.assertIn("child1", node_ids)
        self.assertIn("child2", node_ids)


class TestLogManagerTabIsolation(unittest.TestCase):
    def setUp(self):
        self.log_manager = LogManager()
        self.log_manager.clear()
        self.log_manager._stopped = False
        self.log_manager._stopped_tabs.clear()

    def test_set_stopped_global(self):
        self.log_manager.set_stopped(True)
        self.assertTrue(self.log_manager.is_stopped())

    def test_set_stopped_per_tab(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        self.assertTrue(self.log_manager.is_stopped(tab_name="tab1"))
        self.assertFalse(self.log_manager.is_stopped(tab_name="tab2"))
        self.assertFalse(self.log_manager.is_stopped())

    def test_set_stopped_clear_tabs_on_global(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        self.log_manager.set_stopped(True)
        self.assertTrue(self.log_manager.is_stopped())

    def test_suppress_log_for_stopped_tab(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        entry = LogEntry(level=LogLevel.SUCCESS, tab_name="tab1")
        self.assertTrue(self.log_manager._should_suppress_log(entry))

    def test_dont_suppress_log_for_running_tab(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        entry = LogEntry(level=LogLevel.SUCCESS, tab_name="tab2")
        self.assertFalse(self.log_manager._should_suppress_log(entry))

    def test_dont_suppress_info_log(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        entry = LogEntry(level=LogLevel.INFO, tab_name="tab1")
        self.assertFalse(self.log_manager._should_suppress_log(entry))

    def test_clear_tab_entries(self):
        self.log_manager.log_success("test", "node1", tab_name="tab1")
        self.log_manager.log_success("test", "node2", tab_name="tab2")
        self.log_manager.log_info("test", "node3", tab_name="tab1")
        self.log_manager.clear_tab_entries("tab1")
        entries = self.log_manager.flush()
        tab_names = [e.tab_name for e in entries]
        self.assertNotIn("tab1", [e.tab_name for e in entries if e.level in (LogLevel.SUCCESS, LogLevel.FAILURE)])
        tab2_entries = [e for e in entries if e.tab_name == "tab2"]
        self.assertEqual(len(tab2_entries), 1)

    def test_discard_stopped_tab(self):
        self.log_manager.set_stopped(True, tab_name="tab1")
        self.log_manager.set_stopped(False, tab_name="tab1")
        self.assertFalse(self.log_manager.is_stopped(tab_name="tab1"))


class TestGuiTabManagerDelegation(unittest.TestCase):
    def test_start_tab_uses_delegate(self):
        manager = GuiTabManager()
        delegate_called = []

        def on_start(tab_id):
            delegate_called.append(tab_id)
            return True

        manager.on_tab_start_request = on_start
        result = manager.start_tab("tab_1")
        self.assertTrue(result)
        self.assertEqual(delegate_called, ["tab_1"])

    def test_stop_tab_uses_delegate(self):
        manager = GuiTabManager()
        delegate_called = []

        def on_stop(tab_id):
            delegate_called.append(tab_id)
            return True

        manager.on_tab_stop_request = on_stop
        result = manager.stop_tab("tab_1")
        self.assertTrue(result)
        self.assertEqual(delegate_called, ["tab_1"])

    def test_start_tab_fallback_without_delegate(self):
        manager = GuiTabManager()
        result = manager.start_tab("nonexistent")
        self.assertFalse(result)

    def test_stop_tab_fallback_without_delegate(self):
        manager = GuiTabManager()
        result = manager.stop_tab("nonexistent")
        self.assertFalse(result)


class TestRemoveTabSwitchesToAdjacent(unittest.TestCase):
    def test_remove_active_switches_to_adjacent(self):
        manager = GuiTabManager()
        for i in range(3):
            instance = TreeInstance(
                name=f"test_{i}",
                engine=BehaviorTreeEngine(None),
                context=ExecutionContext(),
                blackboard=Blackboard()
            )
            manager.add_tab(f"tab_{i + 1}", instance)

        manager.switch_tab("tab_2")
        self.assertEqual(manager.active_tab_id, "tab_2")

        manager.remove_tab("tab_2")
        self.assertNotEqual(manager.active_tab_id, "tab_2")

    def test_remove_last_tab(self):
        manager = GuiTabManager()
        instance = TreeInstance(
            name="only",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        manager.add_tab("tab_1", instance)
        manager.remove_tab("tab_1")
        self.assertIsNone(manager.active_tab_id)

    def test_remove_first_of_multiple(self):
        manager = GuiTabManager()
        for i in range(3):
            instance = TreeInstance(
                name=f"test_{i}",
                engine=BehaviorTreeEngine(None),
                context=ExecutionContext(),
                blackboard=Blackboard()
            )
            manager.add_tab(f"tab_{i + 1}", instance)

        manager.switch_tab("tab_1")
        manager.remove_tab("tab_1")
        self.assertIsNotNone(manager.active_tab_id)


class TestTreeInstanceModified(unittest.TestCase):
    def test_modified_default_false(self):
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        self.assertFalse(instance.modified)

    def test_set_modified(self):
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        instance.modified = True
        self.assertTrue(instance.modified)


if __name__ == "__main__":
    unittest.main()
