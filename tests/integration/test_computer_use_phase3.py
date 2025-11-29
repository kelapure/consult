"""
Phase 3 computer-use scenarios:
- Multi-step wizard navigation with validation (3.16)
- Validation error detection and retry (3.17)
- Network timeout recovery (3.18)
"""

import pytest
from pathlib import Path
import sys

from dotenv import load_dotenv
from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.computer_use import BrowserAutomation

load_dotenv()

PROVIDERS = ("gemini", "claude")


def _provider_available(automation: BrowserAutomation, provider: str) -> bool:
    if provider == "gemini":
        return automation.gemini_client is not None
    return automation.anthropic is not None


async def _run_provider_task(automation: BrowserAutomation, provider: str, **kwargs):
    if provider == "gemini":
        return await automation.gemini_computer_use(**kwargs)
    return await automation.claude_computer_use(**kwargs)


@pytest.fixture
def multi_step_url():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "multi_step_form.html"
    return f"file://{fixture_path}"


@pytest.fixture
def validation_retry_url():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "validation_retry_form.html"
    return f"file://{fixture_path}"


@pytest.fixture
def network_timeout_url():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "network_timeout_form.html"
    return f"file://{fixture_path}"


def _assert_local_storage_status(automation: BrowserAutomation, key: str, expected: str = "success"):
    status = automation.last_page_state.get("localStorage", {}).get(key)
    assert status == expected, f"Expected {key}={expected}, got {status}"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_multi_step_wizard_completion(provider, multi_step_url):
    """
    Scenario 3.16: Multi-step navigation with validation gates.
    The AI must handle Next/Back buttons, satisfy validation, and submit successfully.
    """
    automation = BrowserAutomation()

    if not _provider_available(automation, provider):
        pytest.skip(f"{provider.title()} API key not configured")

    logger.info(f"[{provider}] Starting multi-step wizard scenario")

    task = """
    Complete the multi-step expert network application:

    Step 1:
    - Full Name: Alex Martinez
    - Email: alex.martinez@example.com

    Step 2:
    - Industry: Select "Technology / Software"
    - Consultation formats: check BOTH Phone and Video
    - Availability: choose "Within 48 hours"

    Step 3:
    - Areas of Expertise: Provide at least two sentences describing cloud strategy experience.
    - Agree to the confidentiality policy checkbox.

    Use the Next and Back buttons as needed. If a validation error pops up, fix the fields it references.
    Submit the application and wait for the success confirmation.
    """

    try:
        success, actions = await _run_provider_task(
            automation,
            provider,
            task=task,
            url=multi_step_url,
            max_iterations=45,
        )

        assert success, f"{provider} failed multi-step wizard. Actions taken: {len(actions)}"
        assert len(actions) > 0, "No actions were taken"
        _assert_local_storage_status(automation, "multi-step-status")
        assert automation.last_page_state.get("successMessageVisible"), "Success message not detected"
    finally:
        if automation.browser:
            await automation.close_browser()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_validation_error_retry(provider, validation_retry_url):
    """
    Scenario 3.17: Validation error detection and retry.
    First submission always fails until the acknowledgement button is pressed.
    """
    automation = BrowserAutomation()

    if not _provider_available(automation, provider):
        pytest.skip(f"{provider.title()} API key not configured")

    logger.info(f"[{provider}] Starting validation retry scenario")

    task = """
    Submit the profile form with:
    - Profile Name: Jordan Patel
    - Brief Summary: 20 years in capital markets, specializing in fintech partnerships.

    The form will intentionally show a validation error on the first submission.
    When that happens, click the "Acknowledge validation" button that appears,
    then submit the form again to complete the workflow.
    """

    try:
        success, actions = await _run_provider_task(
            automation,
            provider,
            task=task,
            url=validation_retry_url,
            max_iterations=30,
        )

        assert success, f"{provider} failed validation retry scenario. Actions taken: {len(actions)}"
        assert len(actions) > 0, "No actions were taken"
        _assert_local_storage_status(automation, "validation-status")
        assert automation.last_page_state.get("successMessageVisible"), "Success message not detected"
    finally:
        if automation.browser:
            await automation.close_browser()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS)
async def test_network_timeout_recovery(provider, network_timeout_url):
    """
    Scenario 3.18: Network timeout recovery.
    First submission simulates a timeout. The AI must click Retry, then submit again.
    """
    automation = BrowserAutomation()

    if not _provider_available(automation, provider):
        pytest.skip(f"{provider.title()} API key not configured")

    logger.info(f"[{provider}] Starting network timeout recovery scenario")

    task = """
    Fill out the engagement form with:
    - Advisor Name: Casey Nguyen
    - Current Role: Head of Data Platforms
    - Summary: Describe experience building large-scale data mesh programs.

    After the first submission attempt you will see a network timeout message.
    Click the "Retry Submission" button, then submit the form again to finish successfully.
    """

    try:
        success, actions = await _run_provider_task(
            automation,
            provider,
            task=task,
            url=network_timeout_url,
            max_iterations=35,
        )

        assert success, f"{provider} failed network timeout recovery. Actions taken: {len(actions)}"
        assert len(actions) > 0, "No actions were taken"
        _assert_local_storage_status(automation, "network-status")
        assert automation.last_page_state.get("successMessageVisible"), "Success message not detected"
    finally:
        if automation.browser:
            await automation.close_browser()

