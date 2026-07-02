import pytest
import os
import tempfile
import time
from bt_core.file_watcher import SubtreeFileWatcher


class TestSubtreeFileWatcher:
    def test_initialization(self):
        watcher = SubtreeFileWatcher()
        assert watcher._watched_files == {}

    def test_watch_file(self):
        watcher = SubtreeFileWatcher()
        watcher.watch("test.json", "node_1")
        
        assert "test.json" in watcher._watched_files
        assert "node_1" in watcher._watched_files["test.json"]

    def test_unwatch_file(self):
        watcher = SubtreeFileWatcher()
        watcher.watch("test.json", "node_1")
        watcher.unwatch("test.json", "node_1")
        
        assert "node_1" not in watcher._watched_files.get("test.json", set())

    def test_get_watching_nodes(self):
        watcher = SubtreeFileWatcher()
        watcher.watch("test.json", "node_1")
        watcher.watch("test.json", "node_2")
        
        nodes = watcher.get_watching_nodes("test.json")
        
        assert "node_1" in nodes
        assert "node_2" in nodes

    def test_check_changes_with_real_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": true}')
            filepath = f.name
        
        try:
            watcher = SubtreeFileWatcher()
            watcher.watch(filepath, "node_1")
            
            assert watcher.check_changes() == {}
            
            time.sleep(0.1)
            with open(filepath, 'w') as f:
                f.write('{"test": false}')
            
            changed = watcher.check_changes()
            assert filepath in changed
            assert "node_1" in changed[filepath]
        finally:
            os.unlink(filepath)

    def test_unwatch_all_nodes(self):
        watcher = SubtreeFileWatcher()
        watcher.watch("test.json", "node_1")
        watcher.watch("test.json", "node_2")
        watcher.unwatch("test.json")
        
        assert "test.json" not in watcher._watched_files

    def test_notify_changes_callback(self):
        callback_calls = []
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": true}')
            filepath = f.name
        
        try:
            watcher = SubtreeFileWatcher()
            watcher.watch(filepath, "node_1")
            watcher.set_on_file_changed(lambda fp, nid: callback_calls.append((fp, nid)))
            
            time.sleep(0.1)
            with open(filepath, 'w') as f:
                f.write('{"test": false}')
            
            watcher.notify_changes()
            
            assert len(callback_calls) == 1
            assert callback_calls[0][1] == "node_1"
        finally:
            os.unlink(filepath)
