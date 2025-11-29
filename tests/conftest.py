"""Pytest configuration and shared fixtures for testing"""

import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def browser() -> AsyncGenerator[Browser, None]:
    """Launch a browser instance for the test session"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def browser_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create a new browser context for each test"""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="en-US",
    )
    yield context
    await context.close()


@pytest.fixture
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create a new page for each test"""
    page = await browser_context.new_page()
    yield page
    await page.close()


@pytest.fixture
def test_fixture_path() -> Path:
    """Return the path to the test fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_form_url(test_fixture_path: Path) -> str:
    """Return the file:// URL for the simple form fixture"""
    fixture_path = test_fixture_path / "simple_form.html"
    return f"file://{fixture_path}"


@pytest.fixture
def complex_form_url(test_fixture_path: Path) -> str:
    """Return the file:// URL for the complex form fixture"""
    fixture_path = test_fixture_path / "complex_form.html"
    return f"file://{fixture_path}"


# Pytest async configuration
def pytest_configure(config):
    """Configure pytest-asyncio and custom markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (can be skipped with -m 'not slow')"
    )
