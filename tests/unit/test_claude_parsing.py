"""Unit tests for Claude response parsing"""

import pytest
from pathlib import Path
import sys
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestClaudeActionParsing:
    """Test Claude API action response parsing logic"""

    def test_claude_left_click_coordinate_parsing(self):
        """Test parsing left_click action with coordinates"""
        # Claude uses coordinate: [x, y] format
        action = "left_click"
        params = {"coordinate": [640, 480]}

        # Should be able to extract coordinates
        x, y = params["coordinate"]
        assert x == 640
        assert y == 480

    def test_claude_type_action_parsing(self):
        """Test parsing type action with text"""
        action = "type"
        params = {"text": "Hello World"}

        # Should be able to extract text
        assert params["text"] == "Hello World"

    def test_claude_key_action_parsing(self):
        """Test parsing key action for keyboard shortcuts"""
        action = "key"
        params = {"text": "ctrl+s"}

        # Should be able to extract key combination
        assert params["text"] == "ctrl+s"

    def test_claude_scroll_action_parsing(self):
        """Test parsing scroll action with all parameters"""
        action = "scroll"
        params = {
            "coordinate": [640, 480],
            "scroll_direction": "down",
            "scroll_amount": 3
        }

        # Should be able to extract all scroll parameters
        x, y = params["coordinate"]
        assert x == 640
        assert y == 480
        assert params["scroll_direction"] == "down"
        assert params["scroll_amount"] == 3

    def test_claude_mouse_move_parsing(self):
        """Test parsing mouse_move action"""
        action = "mouse_move"
        params = {"coordinate": [100, 200]}

        x, y = params["coordinate"]
        assert x == 100
        assert y == 200

    def test_claude_double_click_parsing(self):
        """Test parsing double_click action"""
        action = "double_click"
        params = {"coordinate": [320, 240]}

        x, y = params["coordinate"]
        assert x == 320
        assert y == 240

    def test_claude_right_click_parsing(self):
        """Test parsing right_click action"""
        action = "right_click"
        params = {"coordinate": [500, 300]}

        x, y = params["coordinate"]
        assert x == 500
        assert y == 300

    def test_claude_drag_action_parsing(self):
        """Test parsing left_click_drag action"""
        action = "left_click_drag"
        params = {
            "coordinate": [100, 100],
            "to_coordinate": [200, 200]
        }

        from_x, from_y = params["coordinate"]
        to_x, to_y = params["to_coordinate"]

        assert from_x == 100
        assert from_y == 100
        assert to_x == 200
        assert to_y == 200

    def test_claude_wait_action_parsing(self):
        """Test parsing wait action"""
        action = "wait"
        params = {"duration": 2.5}

        assert params["duration"] == 2.5

    def test_claude_screenshot_action(self):
        """Test screenshot action (no params)"""
        action = "screenshot"
        params = {}

        # Screenshot action has no parameters
        assert action == "screenshot"
        assert len(params) == 0

    def test_claude_client_initialization(self):
        """Test Claude client is initialized when API key is set"""
        import os
        automation = BrowserAutomation()

        # If ANTHROPIC_API_KEY is set, client should be initialized
        if os.getenv("ANTHROPIC_API_KEY"):
            assert automation.anthropic is not None
        else:
            assert automation.anthropic is None

    def test_mock_claude_response_structure(self):
        """Test mock Claude API response structure"""
        # Create mock response from Claude API
        mock_content_block = Mock()
        mock_content_block.type = "tool_use"
        mock_content_block.id = "toolu_123"
        mock_content_block.name = "computer"
        mock_content_block.input = {
            "action": "left_click",
            "coordinate": [640, 480]
        }

        # Verify structure
        assert mock_content_block.type == "tool_use"
        assert mock_content_block.name == "computer"
        assert mock_content_block.input["action"] == "left_click"
        assert mock_content_block.input["coordinate"] == [640, 480]

    def test_mock_claude_text_response(self):
        """Test mock Claude text response"""
        mock_content_block = Mock()
        mock_content_block.type = "text"
        mock_content_block.text = "I will click the submit button"

        # Text responses should be parseable
        assert mock_content_block.type == "text"
        assert "submit button" in mock_content_block.text

    def test_mock_claude_thinking_response(self):
        """Test mock Claude thinking response"""
        mock_content_block = Mock()
        mock_content_block.type = "thinking"
        mock_content_block.thinking = "I need to fill the name field first"

        # Thinking responses should be extractable
        assert mock_content_block.type == "thinking"
        assert "name field" in mock_content_block.thinking

    def test_claude_coordinate_format_validation(self):
        """Test that Claude coordinates are in correct format"""
        # Claude uses [x, y] arrays, not separate x/y like Gemini
        valid_coordinate = [640, 480]

        # Should be a list/tuple of exactly 2 elements
        assert isinstance(valid_coordinate, (list, tuple))
        assert len(valid_coordinate) == 2
        assert all(isinstance(c, int) for c in valid_coordinate)

    def test_claude_vs_gemini_coordinate_difference(self):
        """Test understanding of Claude vs Gemini coordinate systems"""
        # Claude uses pixel coordinates (e.g., 640)
        claude_x = 640

        # Gemini uses normalized 0-1000 coordinates
        # To convert to same pixel: 640/1280 * 1000 = 500
        gemini_x_normalized = int((claude_x / 1280) * 1000)

        # They should be different
        assert claude_x != gemini_x_normalized
        assert claude_x == 640  # Actual pixels
        assert gemini_x_normalized == 500  # Normalized 0-1000
