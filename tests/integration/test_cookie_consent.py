"""Integration tests for cookie consent handling"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestCookieConsentHandling:
    """Test cookie consent banner detection and handling"""

    @pytest.fixture
    def cookie_consent_url(self):
        """Return URL for cookie consent test fixture"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "cookie_consent.html"
        return f"file://{fixture_path}"

    @pytest.mark.asyncio
    async def test_cookie_banner_visible(self, cookie_consent_url):
        """Test cookie banner is visible on initial load"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            await automation.page.goto(cookie_consent_url)

            # Check banner is visible
            banner = await automation.page.query_selector('#cookie-banner')
            assert banner is not None

            is_visible = await banner.is_visible()
            assert is_visible

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_accept_cookies(self, cookie_consent_url):
        """Test accepting cookies via button click"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            await automation.page.goto(cookie_consent_url)

            # Click accept button
            await automation.page.click('#accept-cookies')

            # Wait for banner to be hidden
            await automation.page.wait_for_function(
                "document.getElementById('cookie-banner').classList.contains('hidden')",
                timeout=2000
            )

            # Check status message
            status_msg = await automation.page.text_content('#status-message')
            assert 'accepted' in status_msg.lower()

            # Check localStorage
            consent_value = await automation.page.evaluate('localStorage.getItem("cookie-consent")')
            assert consent_value == 'accepted'

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_reject_cookies(self, cookie_consent_url):
        """Test rejecting cookies via button click"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            await automation.page.goto(cookie_consent_url)

            # Click reject button
            await automation.page.click('#reject-cookies')

            # Wait for banner to be hidden
            await automation.page.wait_for_function(
                "document.getElementById('cookie-banner').classList.contains('hidden')",
                timeout=2000
            )

            # Check status message
            status_msg = await automation.page.text_content('#status-message')
            assert 'rejected' in status_msg.lower()

            # Check localStorage
            consent_value = await automation.page.evaluate('localStorage.getItem("cookie-consent")')
            assert consent_value == 'rejected'

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_cookie_persistence(self, cookie_consent_url):
        """Test cookie consent persists across page reloads"""
        automation = BrowserAutomation()
        await automation.start_browser(headless=True)

        try:
            # First visit: accept cookies
            await automation.page.goto(cookie_consent_url)
            await automation.page.click('#accept-cookies')
            await automation.page.wait_for_function(
                "document.getElementById('cookie-banner').classList.contains('hidden')",
                timeout=2000
            )

            # Reload page
            await automation.page.reload()

            # Banner should still be hidden
            banner = await automation.page.query_selector('#cookie-banner')
            is_visible = await banner.is_visible()
            assert not is_visible

            # Status should show accepted
            status_msg = await automation.page.text_content('#status-message')
            assert 'accepted' in status_msg.lower()

        finally:
            await automation.close_browser()

    @pytest.mark.asyncio
    async def test_claude_can_handle_cookie_banner(self, cookie_consent_url):
        """Test Claude Computer Use can detect and accept cookie banner"""
        automation = BrowserAutomation()

        # Skip if Claude not configured
        if not automation.anthropic:
            pytest.skip("Claude API key not configured")

        try:
            task = """
            The page has a cookie consent banner at the bottom.
            Click the "Accept All Cookies" button to dismiss it.
            Verify the banner is hidden and status message says cookies are accepted.
            """

            success, actions = await automation.claude_computer_use(
                task=task,
                url=cookie_consent_url,
                max_iterations=10
            )

            # Should succeed
            assert success, f"Claude failed to handle cookie banner. Actions: {actions}"

            # At least one action should be taken
            assert len(actions) > 0

        finally:
            if automation.browser:
                await automation.close_browser()
