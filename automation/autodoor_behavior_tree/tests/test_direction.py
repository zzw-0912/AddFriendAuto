import pytest
from bt_utils.direction import sort_positions_by_direction, SearchDirection


class TestSearchDirection:
    
    def test_constants_exist(self):
        assert SearchDirection.TOP_LEFT == "top-left"
        assert SearchDirection.TOP_RIGHT == "top-right"
        assert SearchDirection.BOTTOM_LEFT == "bottom-left"
        assert SearchDirection.BOTTOM_RIGHT == "bottom-right"
    
    def test_display_names(self):
        assert SearchDirection.DISPLAY_NAMES[SearchDirection.TOP_LEFT] == "左上"
        assert SearchDirection.DISPLAY_NAMES[SearchDirection.TOP_RIGHT] == "右上"
        assert SearchDirection.DISPLAY_NAMES[SearchDirection.BOTTOM_LEFT] == "左下"
        assert SearchDirection.DISPLAY_NAMES[SearchDirection.BOTTOM_RIGHT] == "右下"
    
    def test_value_map(self):
        assert SearchDirection.VALUE_MAP["左上"] == SearchDirection.TOP_LEFT
        assert SearchDirection.VALUE_MAP["右上"] == SearchDirection.TOP_RIGHT
        assert SearchDirection.VALUE_MAP["左下"] == SearchDirection.BOTTOM_LEFT
        assert SearchDirection.VALUE_MAP["右下"] == SearchDirection.BOTTOM_RIGHT


class TestSortPositionsByDirection:
    
    def test_top_left(self):
        positions = [(10, 10), (20, 5), (5, 20), (15, 15)]
        result = sort_positions_by_direction(positions, SearchDirection.TOP_LEFT)
        assert result[0] == (20, 5)
        assert result[-1] == (5, 20)
    
    def test_top_right(self):
        positions = [(10, 10), (20, 5), (5, 20), (15, 15)]
        result = sort_positions_by_direction(positions, SearchDirection.TOP_RIGHT)
        assert result[0] == (20, 5)
    
    def test_bottom_left(self):
        positions = [(10, 10), (20, 5), (5, 20), (15, 15)]
        result = sort_positions_by_direction(positions, SearchDirection.BOTTOM_LEFT)
        assert result[0] == (5, 20)
    
    def test_bottom_right(self):
        positions = [(10, 10), (20, 5), (5, 20), (15, 15)]
        result = sort_positions_by_direction(positions, SearchDirection.BOTTOM_RIGHT)
        assert result[0] == (5, 20)
    
    def test_empty_positions(self):
        result = sort_positions_by_direction([], SearchDirection.TOP_LEFT)
        assert result == []
    
    def test_single_position(self):
        positions = [(100, 200)]
        for direction in [SearchDirection.TOP_LEFT, SearchDirection.TOP_RIGHT, 
                          SearchDirection.BOTTOM_LEFT, SearchDirection.BOTTOM_RIGHT]:
            result = sort_positions_by_direction(positions, direction)
            assert result == [(100, 200)]
    
    def test_same_y_different_x(self):
        positions = [(30, 10), (10, 10), (20, 10)]
        
        result_left = sort_positions_by_direction(positions, SearchDirection.TOP_LEFT)
        assert result_left[0] == (10, 10)
        assert result_left[1] == (20, 10)
        assert result_left[2] == (30, 10)
        
        result_right = sort_positions_by_direction(positions, SearchDirection.TOP_RIGHT)
        assert result_right[0] == (30, 10)
        assert result_right[1] == (20, 10)
        assert result_right[2] == (10, 10)
    
    def test_same_x_different_y(self):
        positions = [(10, 30), (10, 10), (10, 20)]
        
        result_top = sort_positions_by_direction(positions, SearchDirection.TOP_LEFT)
        assert result_top[0] == (10, 10)
        assert result_top[1] == (10, 20)
        assert result_top[2] == (10, 30)
        
        result_bottom = sort_positions_by_direction(positions, SearchDirection.BOTTOM_LEFT)
        assert result_bottom[0] == (10, 30)
        assert result_bottom[1] == (10, 20)
        assert result_bottom[2] == (10, 10)
    
    def test_invalid_direction(self):
        positions = [(10, 10), (20, 20)]
        result = sort_positions_by_direction(positions, "invalid")
        assert result == positions
    
    def test_multiple_positions_grid(self):
        positions = [
            (100, 100),
            (200, 100),
            (300, 100),
            (100, 200),
            (200, 200),
            (300, 200),
            (100, 300),
            (200, 300),
            (300, 300),
        ]
        
        result_top_left = sort_positions_by_direction(positions, SearchDirection.TOP_LEFT)
        assert result_top_left[0] == (100, 100)
        
        result_top_right = sort_positions_by_direction(positions, SearchDirection.TOP_RIGHT)
        assert result_top_right[0] == (300, 100)
        
        result_bottom_left = sort_positions_by_direction(positions, SearchDirection.BOTTOM_LEFT)
        assert result_bottom_left[0] == (100, 300)
        
        result_bottom_right = sort_positions_by_direction(positions, SearchDirection.BOTTOM_RIGHT)
        assert result_bottom_right[0] == (300, 300)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
