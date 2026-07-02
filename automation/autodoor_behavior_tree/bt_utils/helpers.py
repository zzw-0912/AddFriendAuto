import random
from typing import Union


def get_random_value(
    base_value: Union[int, float],
    random_range: Union[int, float] = 0,
    min_value: Union[int, float, None] = None
) -> Union[int, float]:
    """
    计算随机值
    
    Args:
        base_value: 基础值
        random_range: 随机范围（±值），默认为0（不随机）
        min_value: 最小值限制，默认为None（自动为0）
    
    Returns:
        随机后的值
    
    Examples:
        >>> get_random_value(100, 20)
        85  # 随机值在80-120之间
        
        >>> get_random_value(100, 0)
        100  # 无随机范围，返回基础值
        
        >>> get_random_value(50, 30, min_value=0)
        35  # 确保不小于0
    """
    # 确保参数是数值类型
    try:
        base_value = float(base_value) if not isinstance(base_value, (int, float)) else base_value
        random_range = float(random_range) if not isinstance(random_range, (int, float)) else random_range
    except (ValueError, TypeError):
        return base_value
    
    if random_range <= 0:
        return base_value
    
    min_val = base_value - random_range
    max_val = base_value + random_range
    
    if min_value is not None:
        min_val = max(min_value, min_val)
    else:
        min_val = max(0, min_val)
    
    if isinstance(base_value, int):
        return random.randint(int(min_val), int(max_val))
    else:
        return random.uniform(min_val, max_val)


def get_random_duration(base_duration: int, random_range: int = 0) -> int:
    """
    计算随机时长（专用函数，确保时长不为负数）
    
    Args:
        base_duration: 基础时长(ms)
        random_range: 随机范围(±ms)
    
    Returns:
        随机后的时长(ms)
    """
    return get_random_value(base_duration, random_range, min_value=0)


def get_random_interval(base_interval: int, random_range: int = 0) -> int:
    """
    计算随机间隔（专用函数，确保间隔不为负数）
    
    Args:
        base_interval: 基础间隔(ms)
        random_range: 随机范围(±ms)
    
    Returns:
        随机后的间隔(ms)
    """
    return get_random_value(base_interval, random_range, min_value=0)
