import os
import subprocess
import sys
import threading
import queue
import ast
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, List, Optional, Set


class CodeSecurityChecker:
    ALLOWED_AST_NODES: Set[type] = {
        ast.Module, ast.Expr, ast.Constant, ast.Name, ast.Load, ast.Store,
        ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.Num, ast.Str,
        ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp, ast.DictComp,
        ast.Assign, ast.AugAssign, ast.If, ast.While, ast.For, ast.Pass,
        ast.Break, ast.Continue, ast.Return, ast.FunctionDef, ast.Lambda,
        ast.arguments, ast.Call, ast.Attribute, ast.Subscript, ast.Index,
        ast.Slice, ast.ExtSlice, ast.NameConstant, ast.Bytes, ast.Ellipsis,
        ast.Assert, ast.Global, ast.Nonlocal, ast.Await, ast.AsyncFor,
        ast.AsyncWith, ast.AsyncFunctionDef, ast.AnnAssign, ast.FormattedValue,
        ast.JoinedStr, ast.NamedExpr,
    }
    
    FORBIDDEN_NAMES: Set[str] = {
        '__import__', 'eval', 'exec', 'compile', 'open', 'input',
        'breakpoint', 'globals', 'locals', 'vars', 'dir',
        'getattr', 'setattr', 'delattr', 'hasattr',
        '__builtins__', '__class__', '__bases__', '__subclasses__',
        '__mro__', '__dict__', '__globals__',
    }
    
    FORBIDDEN_MODULES: Set[str] = {
        'os.system', 'os.popen', 'os.spawn', 'os.exec',
        'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'ctypes', 'multiprocessing',
    }
    
    @classmethod
    def check_python_script(cls, file_path: str) -> tuple:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if type(node) not in cls.ALLOWED_AST_NODES:
                    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                        continue
                    return False, f"包含受限语法: {type(node).__name__}"
                
                if isinstance(node, ast.Name) and node.id in cls.FORBIDDEN_NAMES:
                    return False, f"包含禁止的函数/变量: {node.id}"
                
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in cls.FORBIDDEN_NAMES:
                            return False, f"调用了禁止的函数: {node.func.id}"
            
            return True, "安全检查通过"
            
        except SyntaxError as e:
            return False, f"语法错误: {e}"
        except Exception as e:
            return False, f"检查异常: {e}"
    
    @classmethod
    def check_path_safety(cls, code_path: str, project_root: str = None) -> tuple:
        if project_root:
            if os.path.isabs(code_path):
                norm_path = os.path.normpath(code_path)
                norm_root = os.path.normpath(project_root)
                if not norm_path.startswith(norm_root + os.sep):
                    return False, "路径遍历风险: 绝对路径超出项目目录"
            else:
                abs_path = os.path.normpath(os.path.join(project_root, code_path))
                norm_root = os.path.normpath(project_root)
                if not abs_path.startswith(norm_root + os.sep):
                    return False, "路径遍历风险: 脚本路径超出项目目录"
        return True, "路径安全"


class CodeNode(ActionNode):
    NODE_TYPE = "CodeNode"
    SKIP_WINDOW_SWITCH = True

    CODE_TYPE_EXTENSIONS = {
        "python": [".py", ".pyw"],
        "batch": [".bat", ".cmd"],
        "powershell": [".ps1"],
    }

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.code_path = self.config.get("code_path", "")
        self.code_type = self.config.get("code_type", "auto")
        self.args: List[str] = self.config.get("args", [])
        self.wait_complete = self.config.get_bool("wait_complete", True)
        self._process: Optional[subprocess.Popen] = None
        self._code_started = False
        self._aborted = False
        self._lock = threading.Lock()
        self._stdout_queue: Optional[queue.Queue] = None
        self._stderr_queue: Optional[queue.Queue] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    def _detect_code_type(self) -> str:
        code_type = self.config.get("code_type", "auto")
        if code_type != "auto":
            return code_type

        _, ext = os.path.splitext(self.config.get("code_path", "").lower())

        for code_type, extensions in self.CODE_TYPE_EXTENSIONS.items():
            if ext in extensions:
                return code_type

        return "python"

    def _get_python_executable(self) -> str:
        if getattr(sys, 'frozen', False):
            return "python"
        return sys.executable

    def _get_startupinfo(self) -> Optional[subprocess.STARTUPINFO]:
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None

    def _build_command(self, code_path: str = None) -> List[str]:
        if code_path is None:
            code_path = self.config.get("code_path", "")

        code_type = self._detect_code_type()

        if code_type == "python":
            cmd = [self._get_python_executable(), "-u", code_path]
        elif code_type == "batch":
            cmd = [code_path]
        elif code_type == "powershell":
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", code_path]
        else:
            cmd = [self._get_python_executable(), "-u", code_path]

        args = self.config.get("args", [])
        if args:
            cmd.extend([str(arg) for arg in args])

        return cmd

    def _read_output(self, pipe, output_queue: queue.Queue) -> None:
        encodings = ['utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
        
        def try_decode(data: bytes) -> str:
            for encoding in encodings:
                try:
                    return data.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    continue
            return data.decode('utf-8', errors='replace')
        
        try:
            for line in iter(pipe.readline, b''):
                if line:
                    decoded = try_decode(line)
                    output_queue.put(decoded)
        finally:
            pipe.close()

    def _flush_output_queues(self) -> None:
        from bt_utils.log_manager import LogManager
        
        if self._stdout_queue:
            while not self._stdout_queue.empty():
                try:
                    line = self._stdout_queue.get_nowait()
                    LogManager.instance().log_info(
                        node_type="代码节点",
                        node_name=self.name,
                        message=line.rstrip()
                    )
                except queue.Empty:
                    break
        
        if self._stderr_queue:
            while not self._stderr_queue.empty():
                try:
                    line = self._stderr_queue.get_nowait()
                    LogManager.instance().log_info(
                        node_type="代码节点",
                        node_name=self.name,
                        message=f"[stderr] {line.rstrip()}"
                    )
                except queue.Empty:
                    break

    def _execute_action(self, context) -> NodeStatus:
        from bt_utils.log_manager import LogManager

        with self._lock:
            self._aborted = False

        try:
            code_path = self.config.get("code_path", "")
            
            if not code_path:
                LogManager.instance().log_failure(
                    node_type="代码节点",
                    node_name=self.name,
                    reason="代码路径为空"
                )
                return NodeStatus.FAILURE
            
            absolute_code_path = code_path
            
            if code_path.startswith("./"):
                if hasattr(context, 'resolve_path') and context.resolve_path:
                    absolute_code_path = context.resolve_path(code_path)
                elif hasattr(context, 'project_root'):
                    project_root = context.project_root
                    absolute_code_path = os.path.join(project_root, code_path[2:])
                else:
                    LogManager.instance().log_failure(
                        node_type="代码节点",
                        node_name=self.name,
                        reason="无法解析相对路径，缺少项目根目录"
                    )
                    return NodeStatus.FAILURE
            else:
                if not os.path.isabs(code_path):
                    absolute_code_path = os.path.abspath(code_path)
            
            if not os.path.exists(absolute_code_path):
                LogManager.instance().log_failure(
                    node_type="代码节点",
                    node_name=self.name,
                    reason=f"代码文件不存在: {absolute_code_path}"
                )
                return NodeStatus.FAILURE
            
            project_root = getattr(context, 'project_root', None)
            path_safe, path_msg = CodeSecurityChecker.check_path_safety(code_path, project_root)
            if not path_safe:
                LogManager.instance().log_failure(
                    node_type="代码节点",
                    node_name=self.name,
                    reason=path_msg
                )
                return NodeStatus.FAILURE
            
            code_type = self._detect_code_type()
            if code_type == "python":
                script_safe, script_msg = CodeSecurityChecker.check_python_script(absolute_code_path)
                if not script_safe:
                    LogManager.instance().log_failure(
                        node_type="代码节点",
                        node_name=self.name,
                        reason=f"脚本安全检查失败: {script_msg}"
                    )
                    return NodeStatus.FAILURE

            if not self.config.get_bool("wait_complete", True):
                cmd = self._build_command(absolute_code_path)
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    startupinfo=self._get_startupinfo(),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                LogManager.instance().log_success(
                    node_type="代码节点",
                    node_name=self.name,
                    message="已启动（不等待完成）"
                )
                return NodeStatus.SUCCESS

            if not self._code_started:
                cmd = self._build_command(absolute_code_path)
                
                LogManager.instance().log_info(
                    node_type="代码节点",
                    node_name=self.name,
                    message=f"启动代码: {' '.join(cmd)}"
                )
                
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    startupinfo=self._get_startupinfo(),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self._code_started = True
                
                self._stdout_queue = queue.Queue()
                self._stderr_queue = queue.Queue()
                self._stdout_thread = threading.Thread(
                    target=self._read_output,
                    args=(self._process.stdout, self._stdout_queue),
                    daemon=True
                )
                self._stderr_thread = threading.Thread(
                    target=self._read_output,
                    args=(self._process.stderr, self._stderr_queue),
                    daemon=True
                )
                self._stdout_thread.start()
                self._stderr_thread.start()
                
                return NodeStatus.RUNNING
            
            with self._lock:
                if self._aborted:
                    return NodeStatus.FAILURE
            
            if not context.check_running():
                self._terminate_process()
                return NodeStatus.ABORTED
            
            if self._process is None:
                return NodeStatus.FAILURE
            
            self._flush_output_queues()
            
            poll_result = self._process.poll()
            if poll_result is None:
                return NodeStatus.RUNNING
            
            self._flush_output_queues()
            
            self._code_started = False
            self._process = None
            self._stdout_queue = None
            self._stderr_queue = None
            self._stdout_thread = None
            self._stderr_thread = None
            
            if poll_result == 0:
                LogManager.instance().log_success(
                    node_type="代码节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="代码节点",
                    node_name=self.name,
                    reason=f"执行失败 (退出码: {poll_result})"
                )
                return NodeStatus.FAILURE

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"CodeNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="代码节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    def _terminate_process(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=1)
            except Exception:
                pass
        self._process = None
        self._code_started = False

    def abort(self, context) -> None:
        with self._lock:
            self._aborted = True
        
        self._terminate_process()
        super().abort(context)
    
    def reset(self, reset_counters: bool = True) -> None:
        self._terminate_process()
        self._aborted = False
        self._stdout_queue = None
        self._stderr_queue = None
        self._stdout_thread = None
        self._stderr_thread = None
        super().reset(reset_counters=reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.code_path = config.get("code_path", "")
        node.code_type = config.get("code_type", "auto")
        node.args = config.get("args", [])
        node.wait_complete = config.get_bool("wait_complete", True)
        return node
