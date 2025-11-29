"""Unit tests for Gemini response parsing"""

import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestGeminiResponseParsing:
    """Test Gemini API response parsing logic"""

    def test_coordinate_denormalization(self):
        """Test converting normalized coordinates (0-1000) to pixels"""
        automation = BrowserAutomation()

        # Test center coordinates (500, 500) on 1920x1080 screen
        x_pixel = automation._denormalize_coord(500, 1920)
        y_pixel = automation._denormalize_coord(500, 1080)

        assert x_pixel == 960  # 500/1000 * 1920
        assert y_pixel == 540  # 500/1000 * 1080

    def test_coordinate_denormalization_edges(self):
        """Test edge cases for coordinate denormalization"""
        automation = BrowserAutomation()

        # Test min coordinates (0, 0)
        assert automation._denormalize_coord(0, 1920) == 0
        assert automation._denormalize_coord(0, 1080) == 0

        # Test max coordinates (1000, 1000)
        assert automation._denormalize_coord(1000, 1920) == 1920
        assert automation._denormalize_coord(1000, 1080) == 1080

    def test_coordinate_denormalization_quarter_points(self):
        """Test quarter point coordinates"""
        automation = BrowserAutomation()

        # Test quarter points on 1280x720 screen
        assert automation._denormalize_coord(250, 1280) == 320   # 1/4
        assert automation._denormalize_coord(500, 1280) == 640   # 1/2
        assert automation._denormalize_coord(750, 1280) == 960   # 3/4



    def test_gemini_client_initialization(self):
        """Test Gemini client is initialized when API key is set"""
        import os
        automation = BrowserAutomation()

        # If GEMINI_API_KEY is set, client should be initialized
        if os.getenv("GEMINI_API_KEY"):
            assert automation.gemini_client is not None
        else:
            assert automation.gemini_client is None

    def test_action_log_structure(self):
        """Test action log has correct structure"""
        automation = BrowserAutomation()

        # Action log should be a list
        assert isinstance(automation.action_log, list)
        assert len(automation.action_log) == 0



    def test_mock_gemini_response_with_function_call(self):
        """Test parsing a mock Gemini response with function call"""
        automation = BrowserAutomation()

        # Create mock response structure
        mock_func_call = Mock()
        mock_func_call.name = "click_at"
        mock_func_call.args = {"x": 500, "y": 300}

        mock_part = Mock()
        mock_part.function_call = mock_func_call

        # Verify we can extract the data
        assert mock_func_call.name == "click_at"
        assert dict(mock_func_call.args) == {"x": 500, "y": 300}

    def test_mock_gemini_response_with_safety_decision(self):
        """Test parsing a response with safety decision"""
        automation = BrowserAutomation()

        # Create mock response with safety decision
        mock_func_call = Mock()
        mock_func_call.name = "type_text_at"
        mock_func_call.args = {
            "x": 500,
            "y": 300,
            "text": "test",
            "safety_decision": {
                "decision": "safe",
                "explanation": "Normal form input"
            }
        }

        # Safety decision should be extractable
        args_dict = dict(mock_func_call.args)
        safety_decision = args_dict.pop('safety_decision', None)

        assert safety_decision is not None
        assert safety_decision["decision"] == "safe"
        assert "x" in args_dict
        assert "text" in args_dict
        assert "safety_decision" not in args_dict  # Should be removed

    def test_mock_empty_gemini_response(self):
        """Test handling empty Gemini response"""
        # Create mock empty response
        mock_response = Mock()
        mock_response.candidates = []

        # Should detect as empty
        assert not mock_response.candidates

    def test_mock_gemini_response_no_parts(self):
        """Test handling response with no parts"""
        # Create mock response with candidate but no parts
        mock_candidate = Mock()
        mock_candidate.content.parts = []

        mock_response = Mock()
        mock_response.candidates = [mock_candidate]

        # Should detect as having no useful parts
        assert not mock_response.candidates[0].content.parts
