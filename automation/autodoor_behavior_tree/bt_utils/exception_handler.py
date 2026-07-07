import functools
import traceback
from typing import Type, Callable, Any, Optional


def log_exception(
    exc: Exception,
    context: str = "",
    include_traceback: bool = True
) -> None:
    """将异常信息输出到终端日志（不输出到 GUI 运行日志）
    
    Args:
        exc: 异常对象
        context: 上下文描述（如函数名、节点名等）
        include_traceback: 是否包含完整堆栈信息
    """
    from bt_utils.log_manager import LogManager
    
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    
    if context:
        message = f"[异常] {context}: {exc_type}: {exc_msg}"
    else:
        message = f"[异常] {exc_type}: {exc_msg}"
    
    if include_traceback:
        tb_str = traceback.format_exc()
        if tb_str and tb_str != "NoneType: None\n":
            message = f"{message}\n{tb_str}"
    
    LogManager.debug_print(message)


def handle_exception(
    *exceptions: Type[Exception],
    default_return: Any = None,
    context: str = "",
    include_traceback: bool = True
) -> Callable:
    """异常处理装饰器，将异常输出到终端日志
    
    Args:
        *exceptions: 要捕获的异常类型
        default_return: 发生异常时的默认返回值
        context: 上下文描述
        include_traceback: 是否包含完整堆栈信息
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                ctx = context or func.__name__
                log_exception(e, ctx, include_traceback)
                return default_return
            except Exception as e:
                ctx = context or func.__name__
                log_exception(e, ctx, include_traceback=True)
                return default_return
        return wrapper
    return decorator


def safe_call(
    func: Callable,
    *args,
    default_return: Any = None,
    context: str = "",
    **kwargs
) -> Any:
    """安全调用函数，捕获异常并输出到终端日志
    
    Args:
        func: 要调用的函数
        *args: 位置参数
        default_return: 发生异常时的默认返回值
        context: 上下文描述
        **kwargs: 关键字参数
    
    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        ctx = context or func.__name__
        log_exception(e, ctx)
        return default_return
