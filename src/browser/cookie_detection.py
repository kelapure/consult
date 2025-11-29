"""Cookie banner and overlay dialog detection utilities.

This module provides CORE (platform-agnostic) capabilities:
- Cookie banner detection and dismissal with retry logic
- Generic overlay/modal dismissal
- Extensible patterns that platforms can extend

Platform-specific dialog handling should be implemented in the
respective platform modules (e.g., src/platforms/glg_platform.py).
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from playwright.async_api import Page
from loguru import logger


# =============================================================================
# CORE COOKIE BANNER PATTERNS (Platform-Agnostic)
# =============================================================================

# Common cookie banner selectors (ordered by priority)
COOKIE_BANNER_SELECTORS = [
    # ID-based (highest priority)
    '#cookie-banner',
    '#cookie-consent',
    '#cookie-notice',
    '#cookieConsent',
    '#cookieBanner',
    '#onetrust-banner-sdk',  # OneTrust (common provider)
    '#CybotCookiebotDialog',  # Cookiebot

    # Class-based
    '.cookie-banner',
    '.cookie-consent',
    '.cookie-notice',
    '.cookieConsent',
    '.consent-banner',
    '.cookie-bar',
    '.cookie-notification',

    # ARIA role-based
    '[role="dialog"][aria-label*="cookie" i]',
    '[role="dialog"][aria-label*="consent" i]',
    '[role="region"][aria-label*="cookie" i]',

    # Data attribute-based
    '[data-cookie-banner]',
    '[data-cookie-consent]',
    '[data-testid*="cookie" i]',
]


# Common accept button selectors (ordered by priority)
ACCEPT_BUTTON_SELECTORS = [
    # ID-based
    '#accept-cookies',
    '#acceptCookies',
    '#cookie-accept',
    '#onetrust-accept-btn-handler',  # OneTrust
    '#CybotCookiebotDialogBodyButtonAccept',  # Cookiebot

    # Class-based
    '.accept-cookies',
    '.cookie-accept',
    '.accept-all',
    '.accept-all-cookies',

    # Text-based (Playwright :has-text pseudo-selector)
    'button:has-text("Accept All")',
    'button:has-text("Allow All Cookies")',
    'button:has-text("Accept Cookies")',
    'button:has-text("Accept")',
    'button:has-text("I Accept")',
    'button:has-text("I Agree")',
    'button:has-text("Agree")',
    'button:has-text("Got it")',
    'button:has-text("OK")',
    'button:has-text("Confirm My Choice")',
    'button:has-text("Confirm")',

    # Link/anchor text-based
    'a:has-text("Accept All")',
    'a:has-text("Accept")',

    # Data attribute-based
    '[data-testid*="accept" i]',
    '[aria-label*="accept" i]',
]


# Generic overlay/modal close button selectors
OVERLAY_CLOSE_SELECTORS = [
    # Close buttons by aria-label
    '[aria-label="Close"]',
    '[aria-label="close"]',
    '[aria-label="Dismiss"]',
    '[aria-label="dismiss"]',

    # Close buttons by class
    '.close-button',
    '.modal-close',
    '.dialog-close',
    '.dismiss-button',

    # Close buttons by text
    'button:has-text("Close")',
    'button:has-text("×")',
    'button:has-text("X")',
    'button:has-text("Dismiss")',
    'button:has-text("No thanks")',
    'button:has-text("Not now")',
    'button:has-text("Skip")',

    # Icon-based close buttons
    '[class*="close-icon"]',
    '[class*="CloseIcon"]',
]


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

async def detect_cookie_banner(page: Page) -> Optional[Dict[str, Any]]:
    """
    Detect if a cookie consent banner is visible on the page.

    Args:
        page: Playwright page object

    Returns:
        Dict with banner info if detected, None otherwise
        {
            "detected": bool,
            "selector": str,
            "visible": bool,
            "text_content": str (first 200 chars)
        }
    """
    for selector in COOKIE_BANNER_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                if is_visible:
                    text = await element.text_content()
                    return {
                        "detected": True,
                        "selector": selector,
                        "visible": True,
                        "text_content": text[:200] if text else ""
                    }
        except Exception:
            continue

    return None


async def find_accept_button(
    page: Page,
    additional_selectors: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Find the accept/agree button for cookie consent.

    Args:
        page: Playwright page object
        additional_selectors: Optional platform-specific button selectors to try first

    Returns:
        Dict with button info if found, None otherwise
        {
            "found": bool,
            "selector": str,
            "text": str,
            "clickable": bool
        }
    """
    # Combine platform-specific selectors with core selectors
    all_selectors = (additional_selectors or []) + ACCEPT_BUTTON_SELECTORS

    for selector in all_selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()
                if is_visible and is_enabled:
                    text = await element.text_content()
                    return {
                        "found": True,
                        "selector": selector,
                        "text": text.strip() if text else "",
                        "clickable": True
                    }
        except Exception:
            continue

    return None


async def auto_accept_cookies(
    page: Page,
    max_retries: int = 3,
    retry_delay: float = 0.5,
    additional_selectors: Optional[List[str]] = None
) -> bool:
    """
    Automatically detect and accept cookie consent with retry logic.

    Args:
        page: Playwright page object
        max_retries: Maximum number of retry attempts for stubborn dialogs
        retry_delay: Delay between retry attempts in seconds
        additional_selectors: Optional platform-specific button selectors

    Returns:
        True if cookies were accepted, False otherwise
    """
    for attempt in range(max_retries):
        # Check if banner exists
        banner = await detect_cookie_banner(page)
        if not banner:
            # No banner found - either accepted or doesn't exist
            return attempt > 0  # Return True if we dismissed it in a previous attempt

        # Find and click accept button
        accept_btn = await find_accept_button(page, additional_selectors)
        if not accept_btn:
            logger.debug(f"Cookie banner found but no accept button (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(retry_delay)
            continue

        try:
            await page.click(accept_btn["selector"], timeout=5000)
            logger.debug(f"Clicked cookie accept button: {accept_btn['text']}")

            # Wait for banner to disappear with timeout
            try:
                await page.wait_for_selector(
                    banner["selector"],
                    state="hidden",
                    timeout=3000
                )
                logger.info("Cookie consent banner dismissed successfully")
                return True
            except Exception:
                # Banner might still be visible, retry
                logger.debug(f"Cookie banner still visible after click (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)

        except Exception as e:
            logger.debug(f"Failed to click cookie accept button: {e}")
            await asyncio.sleep(retry_delay)

    return False


async def dismiss_overlay_dialogs(
    page: Page,
    max_retries: int = 3,
    retry_delay: float = 0.3,
    additional_selectors: Optional[List[str]] = None
) -> int:
    """
    Dismiss generic overlay/modal dialogs that may block interaction.

    This handles non-cookie dialogs like promotional modals, survey popups, etc.

    Args:
        page: Playwright page object
        max_retries: Maximum attempts per dialog type
        retry_delay: Delay between attempts
        additional_selectors: Optional platform-specific close button selectors

    Returns:
        Number of dialogs successfully dismissed
    """
    dismissed_count = 0

    # Combine platform-specific with core selectors
    all_selectors = (additional_selectors or []) + OVERLAY_CLOSE_SELECTORS

    for attempt in range(max_retries):
        dialog_found = False

        for selector in all_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        dialog_found = True
                        await element.click(timeout=3000)
                        dismissed_count += 1
                        logger.debug(f"Dismissed overlay dialog via: {selector}")
                        await asyncio.sleep(retry_delay)
                        break  # Re-scan for other dialogs
            except Exception:
                continue

        if not dialog_found:
            break  # No more dialogs to dismiss

    return dismissed_count


async def dismiss_dialog_by_selectors(
    page: Page,
    dialog_selectors: List[str],
    dismiss_selectors: List[str],
    description: str = "dialog"
) -> bool:
    """
    Dismiss a specific dialog using provided selectors.
    
    This is a generic helper that platforms can use to dismiss
    platform-specific dialogs.

    Args:
        page: Playwright page object
        dialog_selectors: Selectors to detect if dialog is present
        dismiss_selectors: Selectors for buttons to dismiss the dialog
        description: Human-readable description for logging

    Returns:
        True if dialog was found and dismissed, False otherwise
    """
    # Check if dialog is present
    dialog_found = False
    for selector in dialog_selectors:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                dialog_found = True
                break
        except Exception:
            continue

    if not dialog_found:
        return False

    # Try to dismiss with provided selectors
    for selector in dismiss_selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                if is_visible:
                    await element.click(timeout=3000)
                    logger.info(f"Dismissed {description}")
                    await asyncio.sleep(0.3)
                    return True
        except Exception:
            continue

    return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_cookie_banner_priority(selector: str) -> int:
    """
    Get priority rank of a cookie banner selector.

    Args:
        selector: CSS selector

    Returns:
        Priority rank (lower is higher priority)
    """
    try:
        return COOKIE_BANNER_SELECTORS.index(selector)
    except ValueError:
        return 999  # Unknown selector, lowest priority


def is_cookie_related_selector(selector: str) -> bool:
    """
    Check if a selector is likely related to cookie banners.

    Args:
        selector: CSS selector

    Returns:
        True if selector appears cookie-related
    """
    cookie_keywords = [
        'cookie', 'consent', 'banner', 'privacy',
        'gdpr', 'ccpa', 'onetrust', 'cookiebot'
    ]

    selector_lower = selector.lower()
    return any(keyword in selector_lower for keyword in cookie_keywords)
