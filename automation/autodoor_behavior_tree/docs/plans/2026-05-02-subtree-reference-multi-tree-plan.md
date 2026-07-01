# 子树引用与多行为树并行 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 AutoDoor 行为树系统实现子树引用机制和多行为树并行管理功能。

**Architecture:** 采用扩展式设计，新增 SubtreeNode 继承 CompositeNode，NamespacedBlackboard 代理 Blackboard，CycleDetector 静态检测循环引用，MultiTreeManager 管理多引擎实例。GUI 层新增 SubtreeNodeItem 支持展开/折叠预览。

**Tech Stack:** Python 3.10+, CustomTkinter, Tkinter Canvas, threading, dataclasses

---

## 阶段一：核心基础设施

### Task 1: ExecutionContext 子树追踪扩展

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_core\context.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_context_subtree.py`

**Step 1: Write the failing test**

```python
# tests/test_context_subtree.py
import pytest
from bt_core.context import ExecutionContext


class TestExecutionContextSubtree:
    def test_subtree_stack_initialization(self):
        """测试子树栈初始化为空"""
        ctx = ExecutionContext()
        assert hasattr(ctx, '_subtree_stack')
        assert ctx._subtree_stack == []
    
    def test_push_subtree(self):
        """测试压入子树路径"""
        ctx = ExecutionContext()
        ctx.push_subtree("subtrees/login.json")
        assert ctx.get_subtree_depth() == 1
        assert ctx.is_in_subtree("subtrees/login.json")
    
    def test_pop_subtree(self):
        """测试弹出子树路径"""
        ctx = ExecutionContext()
        ctx.push_subtree("subtrees/login.json")
        ctx.push_subtree("subtrees/action.json")
        assert ctx.get_subtree_depth() == 2
        
        popped = ctx.pop_subtree()
        assert popped == "subtrees/action.json"
        assert ctx.get_subtree_depth() == 1
    
    def test_can_enter_subtree(self):
        """测试子树深度限制"""
        ctx = ExecutionContext()
        for i in range(10):
            assert ctx.can_enter_subtree() == (i < 10)
            ctx.push_subtree(f"subtree_{i}.json")
        
        assert ctx.can_enter_subtree() == False
    
    def test_parent_context_reference(self):
        """测试父上下文引用"""
        parent = ExecutionContext()
        child = ExecutionContext()
        child._parent_context = parent
        
        assert child._parent_context is parent
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_context_subtree.py -v`

Expected: FAIL with "AttributeError: 'ExecutionContext' object has no attribute '_subtree_stack'"

**Step 3: Write minimal implementation**

```python
# bt_core/context.py
# 在 __init__ 方法中添加以下属性（约第25行后）

from typing import List, Optional, TYPE_CHECKING

class ExecutionContext:
    MAX_SUBTREE_DEPTH = 10
    
    def __init__(self, project_root: str = None):
        self.blackboard = Blackboard()
        self.elapsed_time: float = 0.0
        self.tick_count: int = 0
        self.project_root = project_root or os.getcwd()
        self._is_running = True
        self._is_paused = False
        self._on_node_status: Optional[Callable] = None
        self._screenshot_manager = None
        self._input_controller = None
        self._ocr_manager = None
        self._alarm_player = None
        self._path_resolver = None
        self._stats_collector = None
        self._bound_window: Optional[int] = None
        self._previous_foreground_window: Optional[int] = None
        
        # 新增：子树追踪
        self._subtree_stack: List[str] = []
        self._parent_context: Optional['ExecutionContext'] = None
    
    def push_subtree(self, subtree_path: str) -> None:
        """进入子树时压栈"""
        self._subtree_stack.append(subtree_path)
    
    def pop_subtree(self) -> Optional[str]:
        """退出子树时出栈"""
        return self._subtree_stack.pop() if self._subtree_stack else None
    
    def get_subtree_depth(self) -> int:
        """获取当前子树嵌套深度"""
        return len(self._subtree_stack)
    
    def is_in_subtree(self, path: str) -> bool:
        """检查路径是否已在引用链中"""
        import os
        normalized_path = os.path.normpath(os.path.abspath(path))
        for p in self._subtree_stack:
            if os.path.normpath(os.path.abspath(p)) == normalized_path:
                return True
        return False
    
    def can_enter_subtree(self) -> bool:
        """检查是否可以进入新的子树"""
        return len(self._subtree_stack) < self.MAX_SUBTREE_DEPTH
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_context_subtree.py -v`

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_context_subtree.py bt_core/context.py
git commit -m "feat(core): add subtree tracking to ExecutionContext"
```

---

### Task 2: NamespacedBlackboard 实现

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_core\blackboard.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_namespaced_blackboard.py`

**Step 1: Write the failing test**

```python
# tests/test_namespaced_blackboard.py
import pytest
from bt_core.blackboard import Blackboard, NamespacedBlackboard


class TestNamespacedBlackboard:
    def test_wrap_key_adds_prefix(self):
        """测试键自动添加命名空间前缀"""
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "login")
        
        assert ns_bb._wrap_key("username") == "login.username"
        assert ns_bb._wrap_key("login.username") == "login.username"
    
    def test_set_writes_to_parent_with_prefix(self):
        """测试 set 写入父黑板（带前缀）"""
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "login")
        
        ns_bb.set("username", "admin")
        
        assert parent.get("login.username") == "admin"
        assert ns_bb.get("username") == "admin"
    
    def test_get_reads_from_parent_with_prefix(self):
        """测试 get 从父黑板读取（带前缀）"""
        parent = Blackboard()
        parent.set("login.username", "admin")
        
        ns_bb = NamespacedBlackboard(parent, "login")
        
        assert ns_bb.get("username") == "admin"
    
    def test_isolation_between_namespaces(self):
        """测试不同命名空间之间隔离"""
        parent = Blackboard()
        
        login_bb = NamespacedBlackboard(parent, "login")
        logout_bb = NamespacedBlackboard(parent, "logout")
        
        login_bb.set("status", "success")
        logout_bb.set("status", "pending")
        
        assert login_bb.get("status") == "success"
        assert logout_bb.get("status") == "pending"
        assert parent.get("login.status") == "success"
        assert parent.get("logout.status") == "pending"
    
    def test_get_all_keys_filters_by_namespace(self):
        """测试获取当前命名空间的所有键"""
        parent = Blackboard()
        parent.set("login.username", "admin")
        parent.set("login.password", "123456")
        parent.set("logout.status", "done")
        
        ns_bb = NamespacedBlackboard(parent, "login")
        
        keys = ns_bb.get_all_keys()
        assert "username" in keys
        assert "password" in keys
        assert "status" not in keys
    
    def test_increment(self):
        """测试递增操作"""
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "counter")
        
        ns_bb.set("value", 0)
        ns_bb.increment("value", 5)
        
        assert ns_bb.get("value") == 5
        assert parent.get("counter.value") == 5
    
    def test_exists(self):
        """测试存在性检查"""
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "test")
        
        assert ns_bb.exists("key") == False
        ns_bb.set("key", "value")
        assert ns_bb.exists("key") == True
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_namespaced_blackboard.py -v`

Expected: FAIL with "ImportError: cannot import name 'NamespacedBlackboard'"

**Step 3: Write minimal implementation**

```python
# bt_core/blackboard.py
# 在文件末尾添加 NamespacedBlackboard 类

class NamespacedBlackboard:
    """命名空间黑板代理
    
    自动为所有键添加命名空间前缀，实现子树黑板隔离。
    对使用者透明，get("x") 实际读写 parent["namespace.x"]
    """
    
    def __init__(self, parent: Blackboard, namespace: str):
        self._parent = parent
        self._namespace = namespace
        self._prefix = f"{namespace}."
    
    def _wrap_key(self, key: str) -> str:
        """添加命名空间前缀"""
        if key.startswith(self._prefix):
            return key
        return f"{self._prefix}{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._parent.get(self._wrap_key(key), default)
    
    def set(self, key: str, value: Any) -> None:
        self._parent.set(self._wrap_key(key), value)
    
    def increment(self, key: str, amount: int = 1) -> None:
        self._parent.increment(self._wrap_key(key), amount)
    
    def delete(self, key: str) -> None:
        self._parent.delete(self._wrap_key(key))
    
    def exists(self, key: str) -> bool:
        return self._parent.exists(self._wrap_key(key))
    
    def subscribe(self, key: str, callback: Callable) -> None:
        self._parent.subscribe(self._wrap_key(key), callback)
    
    def unsubscribe(self, key: str, callback: Callable) -> None:
        self._parent.unsubscribe(self._wrap_key(key), callback)
    
    def get_all_keys(self) -> List[str]:
        """获取当前命名空间下的所有键（去除前缀）"""
        all_keys = self._parent.get_all_keys()
        return [k[len(self._prefix):] for k in all_keys if k.startswith(self._prefix)]
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_namespaced_blackboard.py -v`

Expected: PASS (7 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_namespaced_blackboard.py bt_core/blackboard.py
git commit -m "feat(core): add NamespacedBlackboard for subtree isolation"
```

---

### Task 3: CycleDetector 实现

**Files:**
- Create: `d:\workspace\autodoor_behavior_tree\bt_core\cycle_detector.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_cycle_detector.py`

**Step 1: Write the failing test**

```python
# tests/test_cycle_detector.py
import pytest
import os
import json
import tempfile
from bt_core.cycle_detector import CycleDetector


class TestCycleDetector:
    def test_check_no_cycle(self):
        """测试无循环引用时返回 True"""
        detector = CycleDetector()
        context_stack = ["main.json", "subtree_a.json"]
        
        result = detector.check(context_stack, "subtree_b.json")
        assert result == True
    
    def test_check_detects_direct_cycle(self):
        """测试检测直接循环引用"""
        detector = CycleDetector()
        context_stack = ["main.json", "subtree_a.json"]
        
        result = detector.check(context_stack, "main.json")
        assert result == False
    
    def test_check_detects_indirect_cycle(self):
        """测试检测间接循环引用"""
        detector = CycleDetector()
        context_stack = ["a.json", "b.json", "c.json"]
        
        result = detector.check(context_stack, "a.json")
        assert result == False
    
    def test_check_with_normalized_paths(self):
        """测试路径标准化后比较"""
        detector = CycleDetector()
        context_stack = ["./subtrees/login.json"]
        
        result = detector.check(context_stack, "subtrees/login.json")
        assert result == False
    
    def test_extract_subtree_refs(self):
        """测试从节点树提取子树引用"""
        from bt_core.nodes import SequenceNode
        from bt_core.config import NodeConfig
        
        detector = CycleDetector()
        
        # 创建模拟的 SubtreeNode（后续实现后替换）
        # 这里先测试空列表
        seq = SequenceNode(config=NodeConfig(name="test"))
        refs = detector._extract_subtree_refs(seq)
        assert refs == []
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_cycle_detector.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.cycle_detector'"

**Step 3: Write minimal implementation**

```python
# bt_core/cycle_detector.py
import os
from typing import List, Dict, Set, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .nodes import Node


class CycleDetector:
    """循环引用检测器
    
    使用 DFS 检测行为树引用链中的循环依赖。
    在子树加载时执行检测，发现循环直接拒绝。
    """
    
    def check(self, subtree_stack: List[str], new_path: str) -> bool:
        """检查添加新路径是否会形成循环
        
        Args:
            subtree_stack: 当前引用链（已加载的子树路径列表）
            new_path: 即将加载的子树路径
            
        Returns:
            True 表示无循环，可以加载；False 表示有循环，拒绝加载
        """
        normalized_new = os.path.normpath(os.path.abspath(new_path))
        
        for existing_path in subtree_stack:
            normalized_existing = os.path.normpath(os.path.abspath(existing_path))
            if normalized_existing == normalized_new:
                return False
        
        return True
    
    def check_with_context(self, context, new_path: str) -> bool:
        """使用 ExecutionContext 检查循环
        
        Args:
            context: 执行上下文（包含 _subtree_stack）
            new_path: 即将加载的子树路径
            
        Returns:
            True 表示无循环；False 表示有循环
        """
        subtree_stack = getattr(context, '_subtree_stack', [])
        return self.check(subtree_stack, new_path)
    
    def build_reference_graph(self, root_path: str, project_root: str = None) -> Dict[str, List[str]]:
        """构建引用关系图（用于可视化调试）
        
        Args:
            root_path: 根行为树路径
            project_root: 项目根目录
            
        Returns:
            {文件路径: [引用的子树路径列表]}
        """
        from .serializer import Serializer
        
        graph = {}
        visited: Set[str] = set()
        
        def traverse(path: str):
            normalized = os.path.normpath(os.path.abspath(path))
            if normalized in visited:
                return
            visited.add(normalized)
            
            try:
                node, _, _ = Serializer.load_from_file(path)
                subtree_refs = self._extract_subtree_refs(node)
                
                resolved_refs = []
                for ref in subtree_refs:
                    if not os.path.isabs(ref):
                        if project_root:
                            ref = os.path.join(project_root, ref)
                    resolved_refs.append(os.path.normpath(os.path.abspath(ref)))
                
                graph[normalized] = resolved_refs
                
                for ref in resolved_refs:
                    if os.path.exists(ref):
                        traverse(ref)
                    
            except Exception:
                pass
        
        traverse(root_path)
        return graph
    
    def _extract_subtree_refs(self, node: 'Node') -> List[str]:
        """从节点树中提取所有子树引用路径"""
        refs = []
        
        # 检查是否是 SubtreeNode
        if hasattr(node, 'subtree_path') and node.subtree_path:
            refs.append(node.subtree_path)
        
        # 递归检查子节点
        for child in getattr(node, 'children', []):
            refs.extend(self._extract_subtree_refs(child))
        
        return refs
    
    def detect_cycle_in_graph(self, graph: Dict[str, List[str]]) -> Optional[List[str]]:
        """检测图中是否存在循环
        
        Args:
            graph: 引用关系图
            
        Returns:
            如果存在循环，返回循环路径；否则返回 None
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []
        
        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # 找到循环
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
            
            path.pop()
            rec_stack.remove(node)
            return None
        
        for node in graph:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result
        
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_cycle_detector.py -v`

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_cycle_detector.py bt_core/cycle_detector.py
git commit -m "feat(core): add CycleDetector for subtree reference validation"
```

---

## 阶段二：SubtreeNode 实现

### Task 4: SubtreeNode 核心实现

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_core\nodes.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_subtree_node.py`

**Step 1: Write the failing test**

```python
# tests/test_subtree_node.py
import pytest
import os
import json
import tempfile
from bt_core.nodes import SubtreeNode
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus
from bt_core.context import ExecutionContext


class TestSubtreeNode:
    def test_initialization(self):
        """测试 SubtreeNode 初始化"""
        config = NodeConfig(name="登录流程")
        config.set("subtree_path", "subtrees/login.json")
        config.set("blackboard_mode", "inherit")
        
        node = SubtreeNode(config=config)
        
        assert node.subtree_path == "subtrees/login.json"
        assert node.blackboard_mode == "inherit"
        assert node._subtree_root is None
    
    def test_blackboard_mode_default(self):
        """测试默认黑板模式"""
        node = SubtreeNode()
        assert node.blackboard_mode == "inherit"
    
    def test_resolve_relative_path(self):
        """测试相对路径解析"""
        config = NodeConfig()
        config.set("subtree_path", "./subtrees/login.json")
        
        node = SubtreeNode(config=config)
        
        ctx = ExecutionContext(project_root="D:/project")
        resolved = node._resolve_path(ctx)
        
        assert resolved.endswith("subtrees/login.json") or resolved.endswith("subtrees\\login.json")
    
    def test_resolve_absolute_path(self):
        """测试绝对路径解析"""
        config = NodeConfig()
        config.set("subtree_path", "D:/project/subtrees/login.json")
        
        node = SubtreeNode(config=config)
        
        ctx = ExecutionContext()
        resolved = node._resolve_path(ctx)
        
        assert resolved == "D:/project/subtrees/login.json"
    
    def test_tick_returns_failure_when_path_empty(self):
        """测试空路径返回 FAILURE"""
        node = SubtreeNode(config=NodeConfig(name="空子树"))
        ctx = ExecutionContext()
        
        status = node.tick(ctx)
        assert status == NodeStatus.FAILURE
    
    def test_tick_returns_failure_when_file_not_found(self):
        """测试文件不存在返回 FAILURE"""
        config = NodeConfig(name="不存在的子树")
        config.set("subtree_path", "nonexistent.json")
        
        node = SubtreeNode(config=config)
        ctx = ExecutionContext()
        
        status = node.tick(ctx)
        assert status == NodeStatus.FAILURE
    
    def test_create_subtree_context_inherit(self):
        """测试 inherit 模式创建上下文"""
        config = NodeConfig()
        config.set("blackboard_mode", "inherit")
        
        node = SubtreeNode(config=config)
        parent_ctx = ExecutionContext()
        parent_ctx.blackboard.set("test_var", "parent_value")
        
        sub_ctx = node._create_subtree_context(parent_ctx)
        
        assert sub_ctx is parent_ctx
        assert sub_ctx.blackboard.get("test_var") == "parent_value"
    
    def test_create_subtree_context_isolated(self):
        """测试 isolated 模式创建上下文"""
        config = NodeConfig()
        config.set("blackboard_mode", "isolated")
        
        node = SubtreeNode(config=config)
        parent_ctx = ExecutionContext()
        parent_ctx.blackboard.set("test_var", "parent_value")
        
        sub_ctx = node._create_subtree_context(parent_ctx)
        
        assert sub_ctx is not parent_ctx
        assert sub_ctx.blackboard.get("test_var") is None
    
    def test_create_subtree_context_namespaced(self):
        """测试 namespaced 模式创建上下文"""
        config = NodeConfig()
        config.set("blackboard_mode", "namespaced")
        config.set("namespace", "login")
        
        node = SubtreeNode(config=config)
        parent_ctx = ExecutionContext()
        
        sub_ctx = node._create_subtree_context(parent_ctx)
        
        from bt_core.blackboard import NamespacedBlackboard
        assert isinstance(sub_ctx.blackboard, NamespacedBlackboard)
        
        sub_ctx.blackboard.set("username", "admin")
        assert parent_ctx.blackboard.get("login.username") == "admin"
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_subtree_node.py -v`

Expected: FAIL with "ImportError: cannot import name 'SubtreeNode' from 'bt_core.nodes'"

**Step 3: Write minimal implementation**

在 `bt_core/nodes.py` 文件末尾添加 SubtreeNode 类：

```python
# bt_core/nodes.py
# 在文件末尾添加（约第800行后）

class SubtreeNode(CompositeNode):
    """子树引用节点
    
    引用外部行为树文件作为子树执行。
    
    配置参数:
        subtree_path: 子树文件路径（相对于项目根目录）
        blackboard_mode: "inherit" | "isolated" | "namespaced"
        namespace: 命名空间前缀（namespaced模式使用）
        auto_reload: 每次执行前重新加载子树（默认False，缓存加载）
    """
    NODE_TYPE = "SubtreeNode"
    
    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.subtree_path = self.config.get("subtree_path", "")
        self.blackboard_mode = self.config.get("blackboard_mode", "inherit")
        self.namespace = self.config.get("namespace", "")
        self.auto_reload = self.config.get_bool("auto_reload", False)
        
        self._subtree_root: Optional[Node] = None
        self._subtree_context: Optional[ExecutionContext] = None
        self._loaded_path: Optional[str] = None
        self._file_modified_time: Optional[float] = None
    
    def tick(self, context: ExecutionContext) -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)
    
    def _tick_internal(self, context: ExecutionContext) -> NodeStatus:
        from bt_utils.log_manager import LogManager
        
        if not self._ensure_loaded(context):
            return NodeStatus.FAILURE
        
        if self._subtree_root is None:
            LogManager.instance().log_failure(
                node_type="子树节点",
                node_name=self.name,
                reason="子树加载失败"
            )
            return NodeStatus.FAILURE
        
        context.push_subtree(self._loaded_path)
        
        try:
            status = self._subtree_root.tick(self._subtree_context)
            
            if status != NodeStatus.RUNNING:
                self._on_subtree_complete(status)
            
            return status
        finally:
            context.pop_subtree()
    
    def _ensure_loaded(self, context: ExecutionContext) -> bool:
        """确保子树已加载，返回是否成功"""
        from bt_utils.log_manager import LogManager
        from .cycle_detector import CycleDetector
        
        resolved_path = self._resolve_path(context)
        if not resolved_path:
            LogManager.instance().log_failure(
                node_type="子树节点",
                node_name=self.name,
                reason="子树路径为空"
            )
            return False
        
        if not os.path.exists(resolved_path):
            LogManager.instance().log_failure(
                node_type="子树节点",
                node_name=self.name,
                reason=f"子树文件不存在: {resolved_path}"
            )
            return False
        
        if self._subtree_root and not self.auto_reload:
            if self._loaded_path == resolved_path:
                if not self._has_file_changed(resolved_path):
                    return True
        
        detector = CycleDetector()
        if not detector.check_with_context(context, resolved_path):
            LogManager.instance().log_failure(
                node_type="子树节点",
                node_name=self.name,
                reason=f"检测到循环引用: {resolved_path}"
            )
            return False
        
        try:
            self._subtree_root, _, _ = Serializer.load_from_file(resolved_path)
            self._loaded_path = resolved_path
            self._file_modified_time = os.path.getmtime(resolved_path)
            
            self._subtree_context = self._create_subtree_context(context)
            
            LogManager.debug_print(f"[SubtreeNode] 加载子树成功: {resolved_path}")
            return True
            
        except Exception as e:
            LogManager.instance().log_failure(
                node_type="子树节点",
                node_name=self.name,
                reason=f"加载子树失败: {e}"
            )
            return False
    
    def _create_subtree_context(self, parent_context: ExecutionContext) -> ExecutionContext:
        """根据 blackboard_mode 创建子树上下文"""
        from .blackboard import NamespacedBlackboard
        
        if self.blackboard_mode == "inherit":
            return parent_context
        
        elif self.blackboard_mode == "isolated":
            sub_context = ExecutionContext(parent_context.project_root)
            return sub_context
        
        elif self.blackboard_mode == "namespaced":
            sub_context = ExecutionContext(parent_context.project_root)
            namespace = self.namespace or self.name or self.node_id
            sub_context.blackboard = NamespacedBlackboard(
                parent_context.blackboard,
                namespace
            )
            sub_context._parent_context = parent_context
            sub_context._subtree_stack = parent_context._subtree_stack.copy()
            return sub_context
        
        return parent_context
    
    def _resolve_path(self, context: ExecutionContext) -> Optional[str]:
        """解析子树路径（相对路径→绝对路径）"""
        if not self.subtree_path:
            return None
        
        if os.path.isabs(self.subtree_path):
            return self.subtree_path
        
        return os.path.join(context.project_root, self.subtree_path)
    
    def _has_file_changed(self, path: str) -> bool:
        """检查文件是否已修改"""
        if self._file_modified_time is None:
            return True
        try:
            current_mtime = os.path.getmtime(path)
            return current_mtime > self._file_modified_time
        except:
            return True
    
    def _on_subtree_complete(self, status: NodeStatus):
        """子树完成时的处理"""
        pass
    
    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        if self._subtree_root:
            self._subtree_root.reset(reset_counters)
    
    def abort(self, context: ExecutionContext) -> None:
        if self._subtree_root and self._subtree_context:
            self._subtree_root.abort(self._subtree_context)
        self._subtree_context = None
        self._children_running = False
        super().abort(context)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["config"]["subtree_path"] = self.subtree_path
        data["config"]["blackboard_mode"] = self.blackboard_mode
        if self.namespace:
            data["config"]["namespace"] = self.namespace
        if self.auto_reload:
            data["config"]["auto_reload"] = self.auto_reload
        return data
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_subtree_node.py -v`

Expected: PASS (9 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_subtree_node.py bt_core/nodes.py
git commit -m "feat(core): add SubtreeNode for external tree references"
```

---

### Task 5: SubtreeNode 注册

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_core\registry.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_registry.py`

**Step 1: Write the failing test**

```python
# tests/test_registry.py (添加到现有文件或新建)
import pytest
from bt_core.registry import NodeRegistry


class TestSubtreeNodeRegistration:
    def test_subtree_node_registered(self):
        """测试 SubtreeNode 已注册"""
        from bt_core.registry import register_all_nodes
        register_all_nodes()
        
        node_class = NodeRegistry.get("SubtreeNode")
        assert node_class is not None
        assert node_class.NODE_TYPE == "SubtreeNode"
    
    def test_create_subtree_node_from_registry(self):
        """测试通过注册表创建 SubtreeNode"""
        from bt_core.registry import register_all_nodes
        register_all_nodes()
        
        data = {
            "id": "test_subtree",
            "type": "SubtreeNode",
            "name": "测试子树",
            "config": {
                "subtree_path": "test.json",
                "blackboard_mode": "namespaced",
                "namespace": "test"
            }
        }
        
        node = NodeRegistry.create_node(data)
        assert node is not None
        assert node.NODE_TYPE == "SubtreeNode"
        assert node.subtree_path == "test.json"
        assert node.blackboard_mode == "namespaced"
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_registry.py -v`

Expected: FAIL with "AssertionError: assert node_class is not None"

**Step 3: Write minimal implementation**

```python
# bt_core/registry.py
# 在 register_core_nodes 和 register_all_nodes 函数中添加 SubtreeNode 注册

def register_core_nodes():
    from .nodes import SequenceNode, SelectorNode, ParallelNode, StartNode, RandomNode, SubtreeNode

    NodeRegistry.register("SequenceNode", SequenceNode)
    NodeRegistry.register("SelectorNode", SelectorNode)
    NodeRegistry.register("ParallelNode", ParallelNode)
    NodeRegistry.register("RandomNode", RandomNode)
    NodeRegistry.register("StartNode", StartNode)
    NodeRegistry.register("SubtreeNode", SubtreeNode)  # 新增


def register_all_nodes():
    from .nodes import SequenceNode, SelectorNode, ParallelNode, StartNode, RandomNode, SubtreeNode
    
    NodeRegistry.register("SequenceNode", SequenceNode)
    NodeRegistry.register("SelectorNode", SelectorNode)
    NodeRegistry.register("ParallelNode", ParallelNode)
    NodeRegistry.register("RandomNode", RandomNode)
    NodeRegistry.register("StartNode", StartNode)
    NodeRegistry.register("SubtreeNode", SubtreeNode)  # 新增
    
    # ... 其余节点注册保持不变 ...
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_registry.py -v`

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_registry.py bt_core/registry.py
git commit -m "feat(core): register SubtreeNode in NodeRegistry"
```

---

## 阶段三：序列化扩展

### Task 6: Serializer 子树引用支持

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_core\serializer.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_serializer_subtree.py`

**Step 1: Write the failing test**

```python
# tests/test_serializer_subtree.py
import pytest
import os
import json
import tempfile
from bt_core.serializer import Serializer
from bt_core.nodes import SubtreeNode, SequenceNode
from bt_core.config import NodeConfig


class TestSerializerSubtree:
    def test_serialize_subtree_node(self):
        """测试序列化 SubtreeNode"""
        config = NodeConfig(name="登录流程")
        config.set("subtree_path", "subtrees/login.json")
        config.set("blackboard_mode", "namespaced")
        config.set("namespace", "login")
        
        subtree = SubtreeNode(config=config)
        
        data = Serializer.serialize(subtree)
        
        assert "nodes" in data
        assert data["version"] == "2.0"
        
        node_data = data["nodes"][subtree.node_id]
        assert node_data["type"] == "SubtreeNode"
        assert node_data["config"]["subtree_path"] == "subtrees/login.json"
        assert node_data["config"]["blackboard_mode"] == "namespaced"
    
    def test_deserialize_subtree_node(self):
        """测试反序列化 SubtreeNode"""
        from bt_core.registry import register_all_nodes
        register_all_nodes()
        
        data = {
            "version": "2.0",
            "format_type": "behavior_tree_standalone",
            "root_node": "sub_1",
            "nodes": {
                "sub_1": {
                    "id": "sub_1",
                    "type": "SubtreeNode",
                    "name": "登录流程",
                    "config": {
                        "subtree_path": "subtrees/login.json",
                        "blackboard_mode": "inherit"
                    }
                }
            },
            "connections": []
        }
        
        root, canvas_state, editor_state = Serializer.deserialize(data)
        
        assert root is not None
        assert root.NODE_TYPE == "SubtreeNode"
        assert root.subtree_path == "subtrees/login.json"
    
    def test_collect_subtree_refs(self):
        """测试收集子树引用"""
        config1 = NodeConfig(name="登录")
        config1.set("subtree_path", "login.json")
        
        config2 = NodeConfig(name="登出")
        config2.set("subtree_path", "logout.json")
        
        subtree1 = SubtreeNode(config=config1)
        subtree2 = SubtreeNode(config=config2)
        
        seq = SequenceNode(config=NodeConfig(name="主流程"))
        seq.add_child(subtree1)
        seq.add_child(subtree2)
        
        refs = {}
        Serializer._collect_subtree_refs(seq, refs, "/project")
        
        assert subtree1.node_id in refs
        assert subtree2.node_id in refs
        assert refs[subtree1.node_id]["path"] == "login.json"
        assert refs[subtree2.node_id]["path"] == "logout.json"
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_serializer_subtree.py -v`

Expected: FAIL with "AttributeError: type object 'Serializer' has no attribute '_collect_subtree_refs'"

**Step 3: Write minimal implementation**

```python
# bt_core/serializer.py
# 在 Serializer 类中添加以下方法

class Serializer:
    # ... 现有代码 ...
    
    @staticmethod
    def serialize_with_subtrees(root_node: Node, 
                                  project_root: str = None,
                                  metadata: Dict[str, Any] = None,
                                  canvas_state: Dict[str, Any] = None,
                                  editor_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """序列化行为树（包含子树引用元数据）"""
        data = Serializer.serialize(root_node, metadata, canvas_state, editor_state)
        data["version"] = "2.1"
        data["format_type"] = "behavior_tree_with_subtrees"
        
        subtree_refs = {}
        Serializer._collect_subtree_refs(root_node, subtree_refs, project_root or os.getcwd())
        
        if subtree_refs:
            data["subtree_references"] = subtree_refs
        
        return data
    
    @staticmethod
    def _collect_subtree_refs(node: Node, refs: Dict[str, Any], project_root: str) -> None:
        """递归收集子树引用信息"""
        if hasattr(node, 'subtree_path') and node.subtree_path:
            resolved_path = node.subtree_path
            if not os.path.isabs(resolved_path):
                resolved_path = os.path.join(project_root, resolved_path)
            
            refs[node.node_id] = {
                "path": node.subtree_path,
                "resolved_path": os.path.normpath(os.path.abspath(resolved_path)),
                "node_count": Serializer._count_nodes_in_file(resolved_path) if os.path.exists(resolved_path) else 0
            }
        
        for child in getattr(node, 'children', []):
            Serializer._collect_subtree_refs(child, refs, project_root)
    
    @staticmethod
    def _count_nodes_in_file(filepath: str) -> int:
        """计算文件中的节点数量"""
        try:
            node, _, _ = Serializer.load_from_file(filepath)
            return Serializer._count_nodes(node)
        except:
            return 0
    
    @staticmethod
    def _count_nodes(node: Node) -> int:
        """递归计算节点数量"""
        count = 1
        for child in getattr(node, 'children', []):
            count += Serializer._count_nodes(child)
        return count
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_serializer_subtree.py -v`

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_serializer_subtree.py bt_core/serializer.py
git commit -m "feat(core): add subtree reference support to Serializer"
```

---

## 阶段四：MultiTreeManager 实现

### Task 7: TreeInstance 数据类

**Files:**
- Create: `d:\workspace\autodoor_behavior_tree\bt_core\tree_instance.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_tree_instance.py`

**Step 1: Write the failing test**

```python
# tests/test_tree_instance.py
import pytest
from bt_core.tree_instance import TreeInstance
from bt_core.engine import BehaviorTreeEngine
from bt_core.context import ExecutionContext
from bt_core.blackboard import Blackboard


class TestTreeInstance:
    def test_initialization(self):
        """测试 TreeInstance 初始化"""
        engine = BehaviorTreeEngine()
        context = ExecutionContext()
        blackboard = Blackboard()
        
        instance = TreeInstance(
            name="test_tree",
            engine=engine,
            context=context,
            blackboard=blackboard
        )
        
        assert instance.name == "test_tree"
        assert instance.engine is engine
        assert instance.context is context
        assert instance.blackboard is blackboard
        assert instance.status == "idle"
    
    def test_status_transitions(self):
        """测试状态转换"""
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        
        assert instance.status == "idle"
        
        instance.status = "running"
        assert instance.status == "running"
        
        instance.status = "paused"
        assert instance.status == "paused"
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_tree_instance.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.tree_instance'"

**Step 3: Write minimal implementation**

```python
# bt_core/tree_instance.py
from dataclasses import dataclass, field
from typing import Optional, Any
from .engine import BehaviorTreeEngine
from .context import ExecutionContext
from .blackboard import Blackboard


@dataclass
class TreeInstance:
    """行为树实例
    
    封装单个行为树实例的运行时状态。
    """
    name: str
    engine: BehaviorTreeEngine
    context: ExecutionContext
    blackboard: Blackboard
    status: str = "idle"  # idle, running, paused, completed, error, stopped
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    tick_count: int = 0
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "name": self.name,
            "status": self.status,
            "error_message": self.error_message,
            "tick_count": self.tick_count,
        }
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_tree_instance.py -v`

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_tree_instance.py bt_core/tree_instance.py
git commit -m "feat(core): add TreeInstance dataclass"
```

---

### Task 8: MultiTreeManager 核心实现

**Files:**
- Create: `d:\workspace\autodoor_behavior_tree\bt_core\tree_manager.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_tree_manager.py`

**Step 1: Write the failing test**

```python
# tests/test_tree_manager.py
import pytest
import os
import json
import tempfile
from bt_core.tree_manager import MultiTreeManager
from bt_core.nodes import SequenceNode
from bt_core.config import NodeConfig


class TestMultiTreeManager:
    def test_initialization(self):
        """测试 MultiTreeManager 初始化"""
        manager = MultiTreeManager()
        
        assert manager._trees == {}
        assert manager._shared_blackboard is None
    
    def test_initialization_with_shared_blackboard(self):
        """测试带共享黑板的初始化"""
        manager = MultiTreeManager(shared_blackboard=True)
        
        assert manager._shared_blackboard is not None
    
    def test_add_tree(self):
        """测试添加行为树"""
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        instance = manager.add_tree("test_tree", root)
        
        assert instance is not None
        assert instance.name == "test_tree"
        assert "test_tree" in manager._trees
    
    def test_add_tree_duplicate_name(self):
        """测试添加重名行为树"""
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        
        with pytest.raises(ValueError):
            manager.add_tree("test_tree", root)
    
    def test_remove_tree(self):
        """测试移除行为树"""
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        result = manager.remove_tree("test_tree")
        
        assert result == True
        assert "test_tree" not in manager._trees
    
    def test_remove_nonexistent_tree(self):
        """测试移除不存在的行为树"""
        manager = MultiTreeManager()
        
        result = manager.remove_tree("nonexistent")
        assert result == False
    
    def test_get_tree_status(self):
        """测试获取行为树状态"""
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        status = manager.get_tree_status("test_tree")
        
        assert status is not None
        assert status["name"] == "test_tree"
        assert status["status"] == "idle"
    
    def test_get_all_status(self):
        """测试获取所有行为树状态"""
        manager = MultiTreeManager()
        root1 = SequenceNode(config=NodeConfig(name="test1"))
        root2 = SequenceNode(config=NodeConfig(name="test2"))
        
        manager.add_tree("tree1", root1)
        manager.add_tree("tree2", root2)
        
        all_status = manager.get_all_status()
        
        assert len(all_status) == 2
        assert "tree1" in all_status
        assert "tree2" in all_status
    
    def test_shared_blackboard_communication(self):
        """测试共享黑板通信"""
        manager = MultiTreeManager(shared_blackboard=True)
        
        root1 = SequenceNode(config=NodeConfig(name="tree1"))
        root2 = SequenceNode(config=NodeConfig(name="tree2"))
        
        instance1 = manager.add_tree("tree1", root1)
        instance2 = manager.add_tree("tree2", root2)
        
        instance1.blackboard.set("shared_var", "value")
        
        assert instance2.blackboard.get("shared_var") == "value"
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_tree_manager.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.tree_manager'"

**Step 3: Write minimal implementation**

```python
# bt_core/tree_manager.py
import threading
from typing import Dict, Optional, Callable, Any
from .engine import BehaviorTreeEngine
from .context import ExecutionContext
from .blackboard import Blackboard
from .nodes import Node
from .tree_instance import TreeInstance


class MultiTreeManager:
    """多行为树管理器
    
    管理多个独立行为树实例的并行运行。
    每个树实例拥有独立的引擎、上下文和黑板。
    可选共享黑板实现树间通信。
    """
    
    def __init__(self, shared_blackboard: bool = False):
        self._trees: Dict[str, TreeInstance] = {}
        self._shared_blackboard = Blackboard() if shared_blackboard else None
        self._lock = threading.Lock()
        self._on_tree_status: Optional[Callable] = None
        self._on_node_status: Optional[Callable] = None
    
    def add_tree(self, name: str, root_node: Node, 
                 blackboard: Blackboard = None,
                 tick_interval: float = 0.01) -> TreeInstance:
        """添加行为树实例
        
        Args:
            name: 实例名称（唯一标识）
            root_node: 根节点
            blackboard: 黑板实例（None则使用共享黑板或新建）
            tick_interval: tick间隔（秒）
            
        Returns:
            TreeInstance 实例
        """
        with self._lock:
            if name in self._trees:
                raise ValueError(f"树实例 '{name}' 已存在")
            
            if blackboard is None:
                blackboard = self._shared_blackboard or Blackboard()
            
            context = ExecutionContext()
            context.blackboard = blackboard
            
            engine = BehaviorTreeEngine(root_node)
            engine._tick_interval = tick_interval
            
            engine._on_status_change = lambda status, *args: self._on_engine_status(name, status, *args)
            
            instance = TreeInstance(
                name=name,
                engine=engine,
                context=context,
                blackboard=blackboard
            )
            
            self._trees[name] = instance
            return instance
    
    def add_tree_from_file(self, name: str, filepath: str,
                           blackboard: Blackboard = None,
                           tick_interval: float = 0.01) -> TreeInstance:
        """从文件添加行为树实例"""
        from .serializer import Serializer
        root_node, _, _ = Serializer.load_from_file(filepath)
        return self.add_tree(name, root_node, blackboard, tick_interval)
    
    def remove_tree(self, name: str) -> bool:
        """移除行为树实例"""
        with self._lock:
            if name not in self._trees:
                return False
            
            instance = self._trees[name]
            if instance.status == "running":
                instance.engine.stop()
            
            del self._trees[name]
            return True
    
    def start_tree(self, name: str) -> bool:
        """启动指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance:
                return False
            
            if instance.status == "running":
                return True
            
            instance.engine.start(instance.context)
            instance.status = "running"
            return True
    
    def stop_tree(self, name: str) -> bool:
        """停止指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance:
                return False
            
            instance.engine.stop()
            instance.status = "stopped"
            return True
    
    def pause_tree(self, name: str) -> bool:
        """暂停指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance or instance.status != "running":
                return False
            
            instance.engine.pause()
            instance.status = "paused"
            return True
    
    def resume_tree(self, name: str) -> bool:
        """恢复指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance or instance.status != "paused":
                return False
            
            instance.engine.resume()
            instance.status = "running"
            return True
    
    def start_all(self) -> None:
        """启动所有行为树"""
        for name in list(self._trees.keys()):
            self.start_tree(name)
    
    def stop_all(self) -> None:
        """停止所有行为树"""
        for name in list(self._trees.keys()):
            self.stop_tree(name)
    
    def get_tree_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定行为树状态"""
        instance = self._trees.get(name)
        if not instance:
            return None
        
        return {
            "name": name,
            "status": instance.status,
            "error": instance.error_message,
            "engine": instance.engine.get_status() if instance.engine else None
        }
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有行为树状态"""
        return {name: self.get_tree_status(name) for name in self._trees}
    
    def _on_engine_status(self, name: str, status: str, *args) -> None:
        """引擎状态变化回调"""
        instance = self._trees.get(name)
        if instance:
            if status == "completed":
                instance.status = "completed"
            elif status == "stopped":
                instance.status = "stopped"
            
            if self._on_tree_status:
                self._on_tree_status(name, status, *args)
    
    def set_on_tree_status(self, callback: Callable) -> None:
        """设置树状态变化回调"""
        self._on_tree_status = callback
    
    def set_on_node_status(self, callback: Callable) -> None:
        """设置节点状态变化回调（应用到所有树）"""
        self._on_node_status = callback
        for instance in self._trees.values():
            instance.engine._on_node_status = callback
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_tree_manager.py -v`

Expected: PASS (8 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_tree_manager.py bt_core/tree_manager.py
git commit -m "feat(core): add MultiTreeManager for parallel tree execution"
```

---

## 阶段五：GUI 集成

### Task 9: constants.py 更新

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_gui\bt_editor\constants.py`

**Step 1: Add SubtreeNode to constants**

```python
# bt_gui/bt_editor/constants.py
# 在 NODE_CATEGORY_MAP 中添加

NODE_CATEGORY_MAP = {
    "StartNode": "start",
    "SequenceNode": "composite",
    "SelectorNode": "composite",
    "ParallelNode": "composite",
    "RandomNode": "composite",
    "SubtreeNode": "composite",  # 新增
    # ... 其余节点 ...
}

# 在 NODE_DISPLAY_NAMES 中添加
NODE_DISPLAY_NAMES = {
    # ... 现有名称 ...
    "SubtreeNode": "子树引用",
}

# 在 NODE_DESCRIPTIONS 中添加
NODE_DESCRIPTIONS = {
    # ... 现有描述 ...
    "SubtreeNode": "引用外部行为树文件作为子树",
}

# 更新 COMPOSITE_NODES
COMPOSITE_NODES = ["SequenceNode", "SelectorNode", "ParallelNode", "RandomNode", "SubtreeNode"]
```

**Step 2: Verify changes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -c "from bt_gui.bt_editor.constants import NODE_CATEGORY_MAP, NODE_DISPLAY_NAMES; print('SubtreeNode' in NODE_CATEGORY_MAP)"`

Expected: True

**Step 3: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add bt_gui/bt_editor/constants.py
git commit -m "feat(gui): add SubtreeNode to editor constants"
```

---

### Task 10: property.py Schema 添加

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_gui\bt_editor\property.py`

**Step 1: Add SubtreeNode schema**

```python
# bt_gui/bt_editor/property.py
# 在 NODE_CONFIG_SCHEMAS 字典中添加（约第150行后）

NODE_CONFIG_SCHEMAS = {
    # ... 现有配置 ...
    
    "SubtreeNode": [
        {"key": "subtree_path", "label": "子树路径", "type": "file", "width": 150,
         "filetypes": [("JSON文件", "*.json"), ("YAML文件", "*.yaml *.yml"), ("所有文件", "*.*")]},
        {"key": "blackboard_mode", "label": "黑板模式", "type": "select", 
         "options": ["inherit", "isolated", "namespaced"], "default": "inherit"},
        {"key": "namespace", "label": "命名空间", "type": "text",
         "hide_if": {"field": "blackboard_mode", "value": ["inherit", "isolated"]}},
        {"key": "auto_reload", "label": "自动重载", "type": "bool", "default": False},
    ],
}
```

**Step 2: Verify changes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -c "from bt_gui.bt_editor.property import NODE_CONFIG_SCHEMAS; print('SubtreeNode' in NODE_CONFIG_SCHEMAS)"`

Expected: True

**Step 3: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add bt_gui/bt_editor/property.py
git commit -m "feat(gui): add SubtreeNode property schema"
```

---

### Task 11: SubtreeNodeItem 实现

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_gui\bt_editor\node_item.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_subtree_node_item.py`

**Step 1: Write the failing test**

```python
# tests/test_subtree_node_item.py
import pytest
import tkinter as tk
from bt_gui.bt_editor.node_item import SubtreeNodeItem


class TestSubtreeNodeItem:
    def test_initialization(self):
        """测试 SubtreeNodeItem 初始化"""
        root = tk.Tk()
        canvas = tk.Canvas(root)
        
        item = SubtreeNodeItem(
            canvas=canvas,
            node_id="test_subtree",
            node_type="SubtreeNode",
            x=100,
            y=100,
            name="登录流程",
            config={"subtree_path": "login.json"}
        )
        
        assert item.node_id == "test_subtree"
        assert item.node_type == "SubtreeNode"
        assert item._expanded == False
        assert item._is_preview == False
        
        root.destroy()
    
    def test_toggle_preview(self):
        """测试切换预览状态"""
        root = tk.Tk()
        canvas = tk.Canvas(root)
        
        item = SubtreeNodeItem(
            canvas=canvas,
            node_id="test",
            node_type="SubtreeNode",
            x=100,
            y=100
        )
        
        assert item._expanded == False
        
        item.toggle_preview()
        assert item._expanded == True
        
        item.toggle_preview()
        assert item._expanded == False
        
        root.destroy()
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_subtree_node_item.py -v`

Expected: FAIL with "ImportError: cannot import name 'SubtreeNodeItem'"

**Step 3: Write minimal implementation**

```python
# bt_gui/bt_editor/node_item.py
# 在文件末尾添加 SubtreeNodeItem 类

class SubtreeNodeItem(NodeItem):
    """子树节点视觉项
    
    特殊渲染：
    - 虚线边框
    - 子树图标
    - 路径标签
    - 展开/折叠按钮
    """
    
    SUBTREE_ICON = "🔗"
    
    def __init__(self, canvas: tk.Canvas, node_id: str, node_type: str, 
                 x: float, y: float, name: str = "", config: dict = None, 
                 enabled: bool = True, zoom: float = 1.0, 
                 pan_x: float = 0, pan_y: float = 0):
        super().__init__(canvas, node_id, node_type, x, y, name, config, enabled, zoom, pan_x, pan_y)
        
        self._expanded = False
        self._preview_items: List[int] = []
        self._subtree_data: Optional[Dict] = None
        self._is_preview = False
        self._is_readonly = False
        
        self.height = 70
    
    def _create_visuals(self):
        """创建子树节点视觉元素（覆盖父类）"""
        shadow_offset = 3
        w = self._scale(self.width)
        h = self._scale(self.height)
        x = self._transform_x(self.x)
        y = self._transform_y(self.y)
        
        self.shadow = self.canvas.create_rectangle(
            x - w/2 + self._scale(shadow_offset),
            y - h/2 + self._scale(shadow_offset),
            x + w/2 + self._scale(shadow_offset),
            y + h/2 + self._scale(shadow_offset),
            fill="#000000",
            stipple="gray50",
            outline="",
            tags=("node_shadow", self.node_id)
        )
        
        self.rect = self.canvas.create_rectangle(
            x - w/2,
            y - h/2,
            x + w/2,
            y + h/2,
            fill=self._dark_colors['node_bg'],
            outline=self._dark_colors['node_border'],
            width=2,
            dash=(5, 3),
            tags=("node", self.node_id)
        )
        
        self.color_bar = self.canvas.create_rectangle(
            x - w/2,
            y - h/2,
            x - w/2 + self._scale(4),
            y + h/2,
            fill="#8B5CF6",
            outline="",
            tags=("node_color", self.node_id)
        )
        
        self.icon_text = self.canvas.create_text(
            x - w/2 + self._scale(15),
            y - self._scale(12),
            text=self.SUBTREE_ICON,
            font=("Segoe UI Emoji", max(8, int(10 * self._zoom))),
            anchor="w",
            tags=("node_icon", self.node_id)
        )
        
        display_name = self._get_display_name()
        self.text = self.canvas.create_text(
            x + self._scale(10),
            y - self._scale(5),
            text=display_name,
            fill=self._dark_colors['text_primary'],
            font=("Microsoft YaHei", max(8, int(10 * self._zoom)), "bold"),
            anchor="center",
            tags=("node_text", self.node_id)
        )
        
        path_display = self._get_short_path()
        self.path_text = self.canvas.create_text(
            x,
            y + self._scale(12),
            text=path_display,
            fill="gray",
            font=("Microsoft YaHei", max(6, int(8 * self._zoom))),
            anchor="center",
            tags=("node_path", self.node_id)
        )
        
        self._draw_ports()
    
    def _get_short_path(self) -> str:
        """获取短路径显示"""
        path = self.config.get("subtree_path", "") if self.config else ""
        if len(path) > 25:
            return "…" + path[-22:]
        return path
    
    def toggle_preview(self):
        """切换预览状态"""
        if self._expanded:
            self._collapse_preview()
        else:
            self._expand_preview()
        self._expanded = not self._expanded
    
    def _expand_preview(self):
        """展开预览"""
        self._load_subtree_data()
        
        if self._subtree_data is None:
            return
        
        self._draw_preview_nodes()
        
        self.path_text = self.canvas.create_text(
            self._transform_x(self.x),
            self._transform_y(self.y) + self._scale(12),
            text="[点击折叠]",
            fill="#8B5CF6",
            font=("Microsoft YaHei", max(6, int(8 * self._zoom))),
            anchor="center",
            tags=("node_path", self.node_id)
        )
    
    def _collapse_preview(self):
        """折叠预览"""
        for item_id in self._preview_items:
            try:
                self.canvas.delete(item_id)
            except:
                pass
        self._preview_items.clear()
        
        self.path_text = self.canvas.create_text(
            self._transform_x(self.x),
            self._transform_y(self.y) + self._scale(12),
            text=self._get_short_path(),
            fill="gray",
            font=("Microsoft YaHei", max(6, int(8 * self._zoom))),
            anchor="center",
            tags=("node_path", self.node_id)
        )
    
    def _load_subtree_data(self):
        """加载子树数据"""
        if self._subtree_data is not None:
            return
        
        path = self.config.get("subtree_path", "") if self.config else ""
        if not path:
            return
        
        try:
            from bt_core.serializer import Serializer
            import os
            if os.path.exists(path):
                node, _, _ = Serializer.load_from_file(path)
                self._subtree_data = node
        except Exception:
            pass
    
    def _draw_preview_nodes(self):
        """绘制预览节点（只读）"""
        pass
    
    def is_readonly(self) -> bool:
        return self._is_readonly
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_subtree_node_item.py -v`

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_subtree_node_item.py bt_gui/bt_editor/node_item.py
git commit -m "feat(gui): add SubtreeNodeItem with expand/collapse preview"
```

---

### Task 12: Canvas 预览节点处理

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_gui\bt_editor\canvas.py`

**Step 1: Add preview node filtering**

在 `canvas.py` 中添加预览节点过滤逻辑：

```python
# bt_gui/bt_editor/canvas.py
# 在 _copy_selected_nodes_to_clipboard 方法中添加过滤

def _copy_selected_nodes_to_clipboard(self):
    """复制选中的节点到剪贴板（过滤预览节点）"""
    # 过滤预览节点
    real_nodes = [nid for nid in self.selected_nodes 
                  if nid in self.nodes and not getattr(self.nodes[nid], '_is_preview', False)]
    
    if not real_nodes:
        return None
    
    # ... 其余复制逻辑 ...
```

**Step 2: Add SubtreeNode creation support**

```python
# bt_gui/bt_editor/canvas.py
# 在 add_node 方法中添加 SubtreeNode 特殊处理

def add_node(self, node_id: str, node_type: str, x: float, y: float, 
             name: str = "", config: dict = None, enabled: bool = True):
    """添加节点到画布"""
    # ...
    
    if node_type == "SubtreeNode":
        from .node_item import SubtreeNodeItem
        node = SubtreeNodeItem(
            self.canvas, node_id, node_type, x, y, name, config, enabled,
            self.zoom, self.pan_x, self.pan_y
        )
    else:
        from .node_item import NodeItem
        node = NodeItem(
            self.canvas, node_id, node_type, x, y, name, config, enabled,
            self.zoom, self.pan_x, self.pan_y
        )
    
    # ...
```

**Step 3: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add bt_gui/bt_editor/canvas.py
git commit -m "feat(gui): add SubtreeNode support and preview filtering to canvas"
```

---

### Task 13: palette.py 更新

**Files:**
- Modify: `d:\workspace\autodoor_behavior_tree\bt_gui\bt_editor\palette.py`

**Step 1: Verify SubtreeNode appears in palette**

由于已在 Task 9 中更新了 `constants.py`，SubtreeNode 应该自动出现在节点面板的组合节点分类中。

验证：
```bash
cd d:\workspace\autodoor_behavior_tree
python -c "from bt_gui.bt_editor.constants import COMPOSITE_NODES; print('SubtreeNode' in COMPOSITE_NODES)"
```

Expected: True

**Step 2: Commit (if changes needed)**

```bash
cd d:\workspace\autodoor_behavior_tree
git add bt_gui/bt_editor/palette.py
git commit -m "feat(gui): SubtreeNode automatically appears in palette"
```

---

## 阶段六：文件监听

### Task 14: SubtreeFileWatcher 实现

**Files:**
- Create: `d:\workspace\autodoor_behavior_tree\bt_core\file_watcher.py`
- Test: `d:\workspace\autodoor_behavior_tree\tests\test_file_watcher.py`

**Step 1: Write the failing test**

```python
# tests/test_file_watcher.py
import pytest
import os
import tempfile
import time
from bt_core.file_watcher import SubtreeFileWatcher


class TestSubtreeFileWatcher:
    def test_initialization(self):
        """测试初始化"""
        watcher = SubtreeFileWatcher()
        
        assert watcher._watched_files == {}
    
    def test_watch_file(self):
        """测试监听文件"""
        watcher = SubtreeFileWatcher()
        
        watcher.watch("test.json", "node_1")
        
        assert "test.json" in watcher._watched_files
        assert "node_1" in watcher._watched_files["test.json"]
    
    def test_unwatch_file(self):
        """测试取消监听"""
        watcher = SubtreeFileWatcher()
        
        watcher.watch("test.json", "node_1")
        watcher.unwatch("test.json", "node_1")
        
        assert "node_1" not in watcher._watched_files.get("test.json", set())
    
    def test_get_watching_nodes(self):
        """测试获取监听某文件的所有节点"""
        watcher = SubtreeFileWatcher()
        
        watcher.watch("test.json", "node_1")
        watcher.watch("test.json", "node_2")
        
        nodes = watcher.get_watching_nodes("test.json")
        
        assert "node_1" in nodes
        assert "node_2" in nodes
```

**Step 2: Run test to verify it fails**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_file_watcher.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'bt_core.file_watcher'"

**Step 3: Write minimal implementation**

```python
# bt_core/file_watcher.py
import os
import threading
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SubtreeFileWatcher:
    """子树文件变更监听器
    
    监听子树文件的变更，通知相关节点重新加载。
    """
    
    _watched_files: Dict[str, Set[str]] = field(default_factory=dict)
    _file_mtimes: Dict[str, float] = field(default_factory=dict)
    _on_file_changed: Optional[Callable] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def watch(self, filepath: str, node_id: str) -> None:
        """开始监听文件
        
        Args:
            filepath: 文件路径
            node_id: 引用该文件的节点ID
        """
        with self._lock:
            if filepath not in self._watched_files:
                self._watched_files[filepath] = set()
            self._watched_files[filepath].add(node_id)
            
            if os.path.exists(filepath):
                self._file_mtimes[filepath] = os.path.getmtime(filepath)
    
    def unwatch(self, filepath: str, node_id: str = None) -> None:
        """取消监听文件
        
        Args:
            filepath: 文件路径
            node_id: 节点ID，为None时取消所有监听
        """
        with self._lock:
            if filepath not in self._watched_files:
                return
            
            if node_id is None:
                del self._watched_files[filepath]
                self._file_mtimes.pop(filepath, None)
            else:
                self._watched_files[filepath].discard(node_id)
                if not self._watched_files[filepath]:
                    del self._watched_files[filepath]
                    self._file_mtimes.pop(filepath, None)
    
    def get_watching_nodes(self, filepath: str) -> Set[str]:
        """获取监听某文件的所有节点"""
        with self._lock:
            return set(self._watched_files.get(filepath, set()))
    
    def check_changes(self) -> Dict[str, Set[str]]:
        """检查所有监听文件的变更
        
        Returns:
            {变更的文件路径: 需要通知的节点ID集合}
        """
        changed = {}
        
        with self._lock:
            for filepath, node_ids in self._watched_files.items():
                if not os.path.exists(filepath):
                    continue
                
                current_mtime = os.path.getmtime(filepath)
                old_mtime = self._file_mtimes.get(filepath)
                
                if old_mtime is None or current_mtime > old_mtime:
                    changed[filepath] = set(node_ids)
                    self._file_mtimes[filepath] = current_mtime
        
        return changed
    
    def set_on_file_changed(self, callback: Callable) -> None:
        """设置文件变更回调"""
        self._on_file_changed = callback
    
    def notify_changes(self) -> None:
        """通知所有变更"""
        changed = self.check_changes()
        
        if self._on_file_changed:
            for filepath, node_ids in changed.items():
                for node_id in node_ids:
                    try:
                        self._on_file_changed(filepath, node_id)
                    except Exception:
                        pass
```

**Step 4: Run test to verify it passes**

Run: `cd d:\workspace\autodoor_behavior_tree && python -m pytest tests/test_file_watcher.py -v`

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
cd d:\workspace\autodoor_behavior_tree
git add tests/test_file_watcher.py bt_core/file_watcher.py
git commit -m "feat(core): add SubtreeFileWatcher for file change detection"
```

---

## 完成检查

### 运行所有测试

```bash
cd d:\workspace\autodoor_behavior_tree
python -m pytest tests/ -v
```

Expected: All tests PASS

### 更新 __init__.py 导出

```python
# bt_core/__init__.py
# 添加新模块的导出

from .cycle_detector import CycleDetector
from .tree_manager import MultiTreeManager
from .tree_instance import TreeInstance
from .file_watcher import SubtreeFileWatcher
```

### 最终提交

```bash
cd d:\workspace\autodoor_behavior_tree
git add .
git commit -m "feat: complete subtree reference and multi-tree parallel implementation"
```

---

## 实现顺序总结

```
阶段一：核心基础设施
├── Task 1: ExecutionContext 子树追踪扩展
├── Task 2: NamespacedBlackboard 实现
└── Task 3: CycleDetector 实现

阶段二：SubtreeNode 实现
├── Task 4: SubtreeNode 核心实现
└── Task 5: SubtreeNode 注册

阶段三：序列化扩展
└── Task 6: Serializer 子树引用支持

阶段四：MultiTreeManager 实现
├── Task 7: TreeInstance 数据类
└── Task 8: MultiTreeManager 核心实现

阶段五：GUI 集成
├── Task 9: constants.py 更新
├── Task 10: property.py Schema 添加
├── Task 11: SubtreeNodeItem 实现
├── Task 12: Canvas 预览节点处理
└── Task 13: palette.py 更新

阶段六：文件监听
└── Task 14: SubtreeFileWatcher 实现
```

---

> 计划创建时间：2026-05-02
> 预计总工作量：14 个任务，每个任务 15-30 分钟
