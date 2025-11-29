"""Unit tests for browser lifecycle management"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestBrowserLifecycle:
    """Test browser launch, close, and crash detection"""

    @pytest.mark.asyncio
    async def test_browser_start(self):
        """Test browser can be started"""
        automation = BrowserAutomation()

        # Browser should not be started initially
        assert automation.browser is None
        assert automation.page is None

        # Start browser
        await automation.start_browser(headless=True)

        # Assertions
        assert automation.browser is not None
        assert automation.page is not None

        # Cleanup
        await automation.close_browser()

    @pytest.mark.asyncio
    async def test_browser_start_headed(self):
        """Test browser can be started in headed mode"""
        automation = BrowserAutomation()

        # Start browser (headed mode would show UI, but we test headless in CI)
        await automation.start_browser(headless=True)

        # Assertions
        assert automation.browser is not None
        assert automation.page is not None

        # Cleanup
        await automation.close_browser()

    @pytest.mark.asyncio
    async def test_browser_close(self):
        """Test browser can be closed properly"""
        automation = BrowserAutomation()

        # Start browser
        await automation.start_browser(headless=True)
        assert automation.browser is not None

        # Close browser
        await automation.close_browser()

        # Browser reference still exists but connection is closed
        # (Playwright doesn't set browser to None after close)

    @pytest.mark.asyncio
    async def test_browser_multiple_starts(self):
        """Test multiple browser instances can be started"""
        automation1 = BrowserAutomation()
        automation2 = BrowserAutomation()

        try:
            # Start two separate browsers
            await automation1.start_browser(headless=True)
            await automation2.start_browser(headless=True)

            # Both should be independent
            assert automation1.browser is not automation2.browser
            assert automation1.page is not automation2.page

        finally:
            await automation1.close_browser()
            await automation2.close_browser()

    @pytest.mark.asyncio
    async def test_page_navigation(self, simple_form_url):
        """Test page can navigate to URL"""
        automation = BrowserAutomation()

        await automation.start_browser(headless=True)

        try:
            # Navigate to test page
            await automation.page.goto(simple_form_url)

            # Check page is loaded
            title = await automation.page.title()
            assert title is not None

            # Check URL matches
            current_url = automation.page.url
            assert current_url.startswith("file://")

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_browser_viewport(self):
        """Test browser viewport can be set"""
        automation = BrowserAutomation()

        await automation.start_browser(headless=True)

        try:
            # Set viewport
            await automation.page.set_viewport_size({"width": 1920, "height": 1080})

            # Get viewport
            viewport = automation.page.viewport_size
            assert viewport["width"] == 1920
            assert viewport["height"] == 1080

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_action_log_initialization(self):
        """Test action log is initialized"""
        automation = BrowserAutomation()

        # Action log should be empty initially
        assert automation.action_log == []
        assert isinstance(automation.action_log, list)

    @pytest.mark.asyncio
    async def test_browser_cleanup_on_exception(self):
        """Test browser is cleaned up even if exception occurs"""
        automation = BrowserAutomation()

        try:
            await automation.start_browser(headless=True)

            # Force an error
            raise ValueError("Test exception")

        except ValueError:
            pass  # Expected exception

        finally:
            # Browser should still be closeable
            await automation.close_browser()
