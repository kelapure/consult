"""Integration tests for Computer Use - Login Flow

These tests use REAL Computer Use (Gemini/Claude AI controlling the browser),
NOT direct Playwright commands.
"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation


class TestComputerUseLogin:
    """Test Computer Use AI can handle login flows"""

    @pytest.fixture
    def login_url(self):
        """Return URL for login form test fixture"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_login.html"
        return f"file://{fixture_path}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["gemini", "claude"])
    async def test_successful_login(self, provider, login_url):
        """Test Computer Use AI can log in successfully for both Gemini and Claude"""
        automation = BrowserAutomation()

        if provider == "gemini":
            if not automation.gemini_client:
                pytest.skip("Gemini API key not configured")
        else: # provider == "claude"
            if not automation.anthropic:
                pytest.skip("Claude API key not configured")

        try:
            task = """
            Log in to this website using the credentials shown on the page:
            - Username: admin
            - Password: password123

            Fill in the username and password fields, then click the Login button.
            Wait for the success message to appear.
            """
            
            if provider == "gemini":
                success, actions = await automation.gemini_computer_use(
                    task=task,
                    url=login_url,
                    max_iterations=25
                )
            else: # provider == "claude"
                success, actions = await automation.claude_computer_use(
                    task=task,
                    url=login_url,
                    max_iterations=25
                )

            assert success, f"{provider} failed to log in. Actions taken: {len(actions)}"
            assert len(actions) > 0, "No actions were taken"

            login_status = automation.last_page_state.get('localStorage', {}).get('login-status')
            assert login_status == 'success', f"Login status: {login_status}"

        finally:
            if automation.browser:
                await automation.close_browser()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["gemini", "claude"])
    async def test_detects_wrong_credentials(self, provider, login_url):
        """Test Computer Use AI can detect login failure for both Gemini and Claude"""
        automation = BrowserAutomation()

        if provider == "gemini":
            if not automation.gemini_client:
                pytest.skip("Gemini API key not configured")
        else: # provider == "claude"
            if not automation.anthropic:
                pytest.skip("Claude API key not configured")

        try:
            task = """
            Try to log in with WRONG credentials:
            - Username: wronguser
            - Password: wrongpass

            Fill in these credentials and click Login.
            You should see an error message saying the login failed.
            Report if you see the error message.
            """

            if provider == "gemini":
                success, actions = await automation.gemini_computer_use(
                    task=task,
                    url=login_url,
                    max_iterations=25
                )
            else: # provider == "claude"
                success, actions = await automation.claude_computer_use(
                    task=task,
                    url=login_url,
                    max_iterations=25
                )

            # May or may not succeed (depends on how AI interprets "report error")
            # But we should verify the login actually failed
            login_status = automation.last_page_state.get('localStorage', {}).get('login-status')
            assert login_status == 'failed', "Wrong credentials should fail login"

        finally:
            if automation.browser:
                await automation.close_browser()
