"""Unit tests for screenshot capture and encoding"""

import base64
import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestScreenshotCapture:
    """Test screenshot capture and base64 encoding"""

    @pytest.mark.asyncio
    async def test_screenshot_capture(self, simple_form_url):
        """Test that screenshot can be captured"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            # Navigate to test page
            await automation.page.goto(simple_form_url)

            # Take screenshot
            screenshot = await automation.take_screenshot()

            # Assertions
            assert screenshot is not None
            assert isinstance(screenshot, bytes)
            assert len(screenshot) > 0

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_screenshot_to_base64(self, simple_form_url):
        """Test screenshot base64 encoding"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            # Navigate to test page
            await automation.page.goto(simple_form_url)

            # Take screenshot
            screenshot = await automation.take_screenshot()

            # Convert to base64
            b64_screenshot = automation.screenshot_to_base64(screenshot)

            # Assertions
            assert b64_screenshot is not None
            assert isinstance(b64_screenshot, str)
            assert len(b64_screenshot) > 0

            # Verify it's valid base64
            decoded = base64.b64decode(b64_screenshot)
            assert decoded == screenshot

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_screenshot_without_browser(self):
        """Test that screenshot fails when browser not started"""
        automation = BrowserAutomation()

        with pytest.raises(ValueError, match="Browser not started"):
            await automation.take_screenshot()

    @pytest.mark.asyncio
    async def test_screenshot_size(self, complex_form_url):
        """Test that screenshot has reasonable size"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            # Navigate to test page
            await automation.page.goto(complex_form_url)

            # Take screenshot
            screenshot = await automation.take_screenshot()

            # Assertions - screenshot should be between 10KB and 5MB
            assert len(screenshot) > 10 * 1024  # > 10KB
            assert len(screenshot) < 5 * 1024 * 1024  # < 5MB

        finally:
            await automation.close_browser()

    def test_base64_encoding_only(self):
        """Test base64 encoding without browser"""
        automation = BrowserAutomation()

        # Create mock screenshot data
        mock_screenshot = b"mock screenshot data"

        # Encode
        b64_screenshot = automation.screenshot_to_base64(mock_screenshot)

        # Verify
        assert isinstance(b64_screenshot, str)
        assert base64.b64decode(b64_screenshot) == mock_screenshot
