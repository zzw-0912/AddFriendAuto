from typing import List, Tuple


class SearchDirection:
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    
    DISPLAY_NAMES = {
        TOP_LEFT: "左上",
        TOP_RIGHT: "右上",
        BOTTOM_LEFT: "左下",
        BOTTOM_RIGHT: "右下",
    }
    
    VALUE_MAP = {
        "左上": TOP_LEFT,
        "右上": TOP_RIGHT,
        "左下": BOTTOM_LEFT,
        "右下": BOTTOM_RIGHT,
    }


def sort_positions_by_direction(
    positions: List[Tuple[int, int]], 
    direction: str
) -> List[Tuple[int, int]]:
    if not positions:
        return positions
    
    if direction == SearchDirection.TOP_LEFT:
        return sorted(positions, key=lambda p: (p[1], p[0]))
    
    elif direction == SearchDirection.TOP_RIGHT:
        return sorted(positions, key=lambda p: (p[1], -p[0]))
    
    elif direction == SearchDirection.BOTTOM_LEFT:
        return sorted(positions, key=lambda p: (-p[1], p[0]))
    
    elif direction == SearchDirection.BOTTOM_RIGHT:
        return sorted(positions, key=lambda p: (-p[1], -p[0]))
    
    return positions
