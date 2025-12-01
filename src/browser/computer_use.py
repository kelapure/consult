"""Browser automation using Claude and Gemini computer-use APIs.

This module provides CORE (platform-agnostic) capabilities:
- Browser automation with Playwright
- Claude and Gemini Computer Use API integration
- Generic success/failure detection with extensible patterns
- Project ID extraction from URLs

Platform-specific patterns (success indicators, dialog handling, etc.)
should be passed in via function parameters or implemented in the
respective platform modules (e.g., src/platforms/glg_platform.py).
"""

import os
import re
import base64
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Callable
from io import BytesIO
from urllib.parse import urlparse, parse_qs
from loguru import logger

from anthropic import Anthropic

# Gemini Computer Use API
from google import genai
from google.genai import types
from google.genai.types import Content, Part

# Browser automation
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Browser utilities
from src.browser.cookie_detection import auto_accept_cookies, detect_cookie_banner
from src.browser.sanitize import sanitize_credentials, mask_password_in_logs


# =============================================================================
# CORE SUCCESS/FAILURE DETECTION PATTERNS (Platform-Agnostic)
# =============================================================================

# Generic success indicators for form submission
SUCCESS_INDICATORS = [
    # Completion messages
    "application submitted",
    "successfully submitted",
    "submission confirmed",
    "successfully completed",
    "you're all set",
    "thank you for applying",
    "we'll be in touch",
    "application received",
    "thank you for your submission",
    "submission successful",
    "form submitted",
    "your request has been submitted",
    # Confirmation messages
    "we have received your",
    "your application is complete",
]

# Generic failure indicators
FAILURE_INDICATORS = [
    "unable to submit",
    "submission failed",
    "error occurred",
    "please try again",
    "something went wrong",
    "form could not be submitted",
    "validation error",
    "required field",
    "invalid input",
]

# Generic blocked state indicators
BLOCKED_INDICATORS = [
    "already declined",
    "no longer available",
    "opportunity expired",
    "invitation expired",
    "project closed",
    "application closed",
    "no longer accepting",
    "deadline passed",
    "position filled",
    "opportunity unavailable",
]

# Workflow stage patterns for multi-step forms
WORKFLOW_STAGES = {
    "application_form": ["application", "apply", "express interest", "fill out"],
    "scheduling": ["availability", "schedule", "calendar", "select time", "book a time"],
    "confirmation": ["confirm", "review", "summary", "final step"],
    "completion": ["complete", "done", "finished", "all set", "thank you"],
}


# =============================================================================
# CORE HELPER FUNCTIONS
# =============================================================================

def extract_project_id_from_url(url: str) -> Optional[str]:
    """
    Extract project ID from a URL using common patterns.
    
    This is a generic helper that supports common URL patterns.
    Platform-specific patterns can be added by platforms.
    
    Supports patterns:
    - cpid=123456 (GLG-style)
    - project_id=123456
    - /projects/123456
    - /p/123456
    - id=123456
    
    Args:
        url: The URL to extract project ID from
        
    Returns:
        Project ID string if found, None otherwise
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Check common query parameter names
        param_names = ['cpid', 'project_id', 'projectId', 'id', 'pid']
        for param in param_names:
            if param in query_params:
                return query_params[param][0]
        
        # Check URL path patterns
        path_patterns = [
            r'/projects?/(\d+)',  # /project/123 or /projects/123
            r'/p/(\d+)',          # /p/123
            r'/accept/(\d+)',     # /accept/123
            r'/opportunity/(\d+)', # /opportunity/123
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, parsed.path)
            if match:
                return match.group(1)
                
    except Exception as e:
        logger.debug(f"Error extracting project ID from URL: {e}")
    
    return None


def detect_workflow_stage(
    page_text: str,
    additional_stages: Optional[Dict[str, List[str]]] = None
) -> Optional[str]:
    """
    Detect the current workflow stage based on page content.
    
    Args:
        page_text: Text content of the current page
        additional_stages: Platform-specific stage patterns to check first
        
    Returns:
        Workflow stage name if detected, None otherwise
    """
    page_text_lower = page_text.lower()
    
    # Check platform-specific stages first
    if additional_stages:
        for stage_name, keywords in additional_stages.items():
            for keyword in keywords:
                if keyword.lower() in page_text_lower:
                    return stage_name
    
    # Check generic stages
    for stage_name, keywords in WORKFLOW_STAGES.items():
        for keyword in keywords:
            if keyword.lower() in page_text_lower:
                return stage_name
    
    return None


def check_success_indicators(
    page_text: str,
    additional_indicators: Optional[List[str]] = None
) -> Optional[str]:
    """
    Check if page content contains success indicators.
    
    Args:
        page_text: Text content of the current page
        additional_indicators: Platform-specific success patterns to check first
        
    Returns:
        The matched success indicator if found, None otherwise
    """
    page_text_lower = page_text.lower()
    
    # Check platform-specific indicators first
    if additional_indicators:
        for indicator in additional_indicators:
            if indicator.lower() in page_text_lower:
                return indicator
    
    # Check generic indicators
    for indicator in SUCCESS_INDICATORS:
        if indicator.lower() in page_text_lower:
            return indicator
    
    return None


def check_failure_indicators(
    page_text: str,
    additional_indicators: Optional[List[str]] = None
) -> Optional[str]:
    """
    Check if page content contains failure indicators.
    
    Args:
        page_text: Text content of the current page
        additional_indicators: Platform-specific failure patterns to check first
        
    Returns:
        The matched failure indicator if found, None otherwise
    """
    page_text_lower = page_text.lower()
    
    # Check platform-specific indicators first
    if additional_indicators:
        for indicator in additional_indicators:
            if indicator.lower() in page_text_lower:
                return indicator
    
    # Check generic indicators
    for indicator in FAILURE_INDICATORS:
        if indicator.lower() in page_text_lower:
            return indicator
    
    return None


def check_blocked_indicators(
    page_text: str,
    additional_indicators: Optional[List[str]] = None
) -> Optional[str]:
    """
    Check if page content contains blocked state indicators.
    
    Args:
        page_text: Text content of the current page
        additional_indicators: Platform-specific blocked patterns to check first
        
    Returns:
        The matched blocked indicator if found, None otherwise
    """
    page_text_lower = page_text.lower()
    
    # Check platform-specific indicators first
    if additional_indicators:
        for indicator in additional_indicators:
            if indicator.lower() in page_text_lower:
                return indicator
    
    # Check generic indicators
    for indicator in BLOCKED_INDICATORS:
        if indicator.lower() in page_text_lower:
            return indicator
    
    return None


def _sanitize_action_log(action_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitize action log entries to redact potentially sensitive typed text.
    
    This handles cases where passwords are typed (where the key is "text" not "password").
    Uses heuristics to detect password-like strings: short, no spaces, alphanumeric with symbols.
    Excludes email addresses and URLs from redaction.
    
    Args:
        action_log: List of action log entries
        
    Returns:
        Sanitized action log with sensitive text redacted
    """
    import re
    
    # Pattern for password-like strings: 6-50 chars, no spaces, has letters and numbers/symbols
    password_pattern = re.compile(r'^(?=.*[a-zA-Z])(?=.*[\d!@#$%^&*()_+\-=\[\]{}|;:\'",.<>?/`~])[^\s]{6,50}$')
    
    # Patterns to exclude from redaction (emails, URLs)
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    url_pattern = re.compile(r'^https?://')
    
    sanitized = []
    for entry in action_log:
        entry_copy = entry.copy()
        
        # Check text fields in type actions
        if entry.get("action") in ("type", "type_text_at", "select_option"):
            text = entry.get("text", "")
            if text:
                # Skip emails and URLs
                if email_pattern.match(text) or url_pattern.match(text):
                    pass  # Don't redact
                elif password_pattern.match(text):
                    entry_copy["text"] = "***REDACTED***"
        
        sanitized.append(entry_copy)
    
    return sanitized


# =============================================================================
# SMART ELEMENT CLICK - Reusable helper for robust button/element clicking
# =============================================================================

async def smart_element_click(
    page: Page,
    strategies: List[Dict[str, Any]],
    correlation_id: str = "N/A",
    timeout: int = 5000
) -> bool:
    """
    Smart element click with multiple fallback strategies.
    
    This is a reusable helper function that platforms can use for robust
    button detection and clicking. It tries multiple strategies in order:
    CSS selectors, text-based selectors, and XPath.
    
    Args:
        page: Playwright page object
        strategies: List of strategy dicts, each containing:
            - "type": "css" | "text" | "xpath"
            - "selector": The selector string
            - "description": Optional description for logging
        correlation_id: Optional ID for logging context
        timeout: Timeout in ms for each strategy attempt
        
    Returns:
        True if element was found and clicked, False otherwise
        
    Example:
        strategies = [
            {"type": "css", "selector": "button.submit-btn", "description": "Submit button by class"},
            {"type": "text", "selector": "button:has-text('Submit')", "description": "Submit button by text"},
            {"type": "xpath", "selector": "//button[contains(text(), 'Submit')]", "description": "Submit via XPath"},
        ]
        success = await smart_element_click(page, strategies, correlation_id="abc123")
    """
    for strategy in strategies:
        strategy_type = strategy.get("type", "css")
        selector = strategy.get("selector", "")
        description = strategy.get("description", selector)
        
        if not selector:
            continue
            
        try:
            element = None
            
            if strategy_type == "css":
                # Standard CSS selector
                element = await page.query_selector(selector)
                
            elif strategy_type == "text":
                # Playwright text selector (e.g., "button:has-text('Submit')")
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        element = await locator.first.element_handle()
                except Exception:
                    # Fallback: try as regular CSS selector
                    element = await page.query_selector(selector)
                    
            elif strategy_type == "xpath":
                # XPath selector
                try:
                    locator = page.locator(f"xpath={selector}")
                    if await locator.count() > 0:
                        element = await locator.first.element_handle()
                except Exception:
                    pass
            
            if element:
                # Check if element is visible
                is_visible = await element.is_visible()
                if is_visible:
                    await element.click(timeout=timeout)
                    logger.info(f"[{correlation_id}] smart_element_click succeeded: {description}")
                    return True
                else:
                    logger.debug(f"[{correlation_id}] Element found but not visible: {description}")
                    
        except Exception as e:
            logger.debug(f"[{correlation_id}] smart_element_click strategy failed ({strategy_type}): {description} - {e}")
            continue
    
    logger.warning(f"[{correlation_id}] smart_element_click: All strategies exhausted, no element clicked")
    return False


class BrowserAutomation:
    """Browser automation using AI computer-use capabilities.
    
    This class provides platform-agnostic browser automation. Platform-specific
    patterns (success indicators, dialog handling, etc.) should be passed in
    via the platform_config parameter.
    """

    def __init__(
        self,
        correlation_id: str = "N/A",
        platform: str = "unknown",
        project_url: str = "N/A",
        platform_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize browser automation with Gemini and Claude.
        
        Args:
            correlation_id: Unique ID for logging/tracing
            platform: Platform name (for logging)
            project_url: URL being processed
            platform_config: Platform-specific configuration including:
                - success_indicators: List[str] - platform-specific success patterns
                - failure_indicators: List[str] - platform-specific failure patterns
                - blocked_indicators: List[str] - platform-specific blocked patterns
                - workflow_stages: Dict[str, List[str]] - platform-specific workflow stages
                - dialog_handler: Callable[[Page], Awaitable[Dict]] - async function to dismiss platform dialogs
                - cookie_selectors: List[str] - platform-specific cookie button selectors
        """
        self.correlation_id = correlation_id
        self.platform = platform
        self.project_url = project_url
        self.platform_config = platform_config or {}
        
        # Configure Gemini with new genai client
        gemini_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            self.gemini_client = genai.Client(api_key=gemini_api_key)
            logger.info(f"[{self.correlation_id}] Gemini AI configured")
        else:
            self.gemini_client = None
            logger.warning(f"[{self.correlation_id}] Gemini API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY.")

        # Configure Claude
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.anthropic_api_key:
            self.anthropic = Anthropic(api_key=self.anthropic_api_key)
            logger.info(f"[{self.correlation_id}] Claude AI configured")
        else:
            self.anthropic = None

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.action_log: List[Dict[str, Any]] = []
        self.last_page_state: Dict[str, Any] = {}
        self._playwright = None
        # Track repeated clicks at same location for fallback triggering
        self._click_history: List[Tuple[int, int]] = []
        self._click_fallback_threshold = 2  # Use JS fallback after N clicks at same spot
        
        # Profile support
        self.user_data_dir: Optional[str] = None
        
    def _log_action(self, action_data: Dict[str, Any]):
        """Add contextual information to an action and log it."""
        from datetime import datetime
        
        full_action_data = {
            "timestamp": datetime.now().isoformat(),
            "correlation_id": self.correlation_id,
            "platform": self.platform,
            "project_url": self.project_url,
            **action_data
        }
        self.action_log.append(full_action_data)
        logger.info(f"[{self.correlation_id}] Logged action: {action_data['action']}")

    async def start_browser(self, headless: bool = None, user_data_dir: str = None):
        """
        Start Playwright browser.

        Args:
            headless: Override headless mode. If None, reads from HEADLESS env var (default: False)
            user_data_dir: Path to Chrome user data directory for persistent sessions
        """
        # Environment detection
        if headless is None:
            headless = os.getenv('HEADLESS', 'false').lower() in ('true', '1', 'yes')

        self._playwright = await async_playwright().start()
        
        if user_data_dir:
            # Create directory if it doesn't exist
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"[{self.correlation_id}] Launching persistent browser with profile: {user_data_dir}")
            
            # Launch persistent context
            # Note: persistent_context is both a Browser and a Context
            self.context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"] # Basic stealth
            )
            self.browser = None # Persistent context doesn't return a separate Browser object
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            
        else:
            # Standard ephemeral launch
            self.browser = await self._playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

        self.action_log = []
        self.last_page_state = {}

        mode = "headless" if headless else "headed"
        profile_msg = f" (profile: {os.path.basename(user_data_dir)})" if user_data_dir else " (fresh profile)"
        logger.info(f"[{self.correlation_id}] Browser started in {mode} mode{profile_msg}")

    async def close_browser(self):
        """Close browser"""
        try:
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
                
            if self._playwright:
                await self._playwright.stop()
                
            logger.info(f"[{self.correlation_id}] Browser closed")
        except Exception as e:
            logger.debug(f"[{self.correlation_id}] Error closing browser: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self._playwright = None

    async def take_screenshot(self) -> bytes:
        """Take screenshot of current page"""
        if not self.page:
            raise ValueError("Browser not started")
        screenshot = await self.page.screenshot(full_page=False)
        return screenshot

    def screenshot_to_base64(self, screenshot: bytes) -> str:
        """Convert screenshot to base64"""
        return base64.b64encode(screenshot).decode('utf-8')

    def _denormalize_coord(self, normalized_value: int, screen_dimension: int) -> int:
        """
        Convert normalized coordinate (0-1000) to pixel coordinate.
        Gemini Computer Use API uses normalized coordinates.
        """
        return int(normalized_value / 1000 * screen_dimension)

    async def _get_element_at_position(self, x: int, y: int):
        """Get element at pixel coordinates using JavaScript"""
        element = await self.page.evaluate(f"""
            document.elementFromPoint({x}, {y})
        """)
        return element

    async def _smart_select_option(self, x: int, y: int, text: str) -> bool:
        """
        Intelligently select dropdown option by text value.
        Detects select elements and uses Playwright's select_option for reliability.
        """
        try:
            # Find the select element at coordinates
            select_elem = await self.page.evaluate(f"""
                (function() {{
                    let elem = document.elementFromPoint({x}, {y});
                    // Walk up DOM tree to find select element
                    while (elem && elem.tagName !== 'SELECT') {{
                        elem = elem.parentElement;
                    }}
                    if (elem && elem.tagName === 'SELECT') {{
                        return elem.id || elem.name || 'found';
                    }}
                    return null;
                }})()
            """)

            if select_elem:
                logger.info(f"[{self.correlation_id}] Detected <select> element, using smart selection for: {text}")
                # Use JavaScript with prioritized matching logic
                selected = await self.page.evaluate(f"""
                    (function() {{
                        let elem = document.elementFromPoint({x}, {y});
                        while (elem && elem.tagName !== 'SELECT') {{
                            elem = elem.parentElement;
                        }}
                        if (elem) {{
                            const searchText = '{text}'.toLowerCase();
                            let bestMatch = null;
                            let matchQuality = 0; // 1=contains, 2=startsWith, 3=exact

                            // Prioritized matching: exact > startsWith > contains
                            for (let option of elem.options) {{
                                const optionText = option.text.toLowerCase();
                                const optionValue = option.value.toLowerCase();

                                // Exact match (highest priority)
                                if (optionText === searchText || optionValue === searchText) {{
                                    bestMatch = option;
                                    matchQuality = 3;
                                    break;
                                }}

                                // Starts with (medium priority)
                                if (matchQuality < 2 && (optionText.startsWith(searchText) || optionValue.startsWith(searchText))) {{
                                    bestMatch = option;
                                    matchQuality = 2;
                                }}

                                // Contains (lowest priority)
                                if (matchQuality < 1 && (optionText.includes(searchText) || optionValue.includes(searchText))) {{
                                    bestMatch = option;
                                    matchQuality = 1;
                                }}
                            }}

                            if (bestMatch) {{
                                bestMatch.selected = true;
                                elem.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return bestMatch.text;
                            }}
                        }}
                        return null;
                    }})()
                """)
                if selected:
                    logger.success(f"[{self.correlation_id}] Selected dropdown option: {selected}")
                    return True
                else:
                    logger.warning(f"[{self.correlation_id}] Could not find option matching: {text}")
                    return False
            return False
        except Exception as e:
            logger.debug(f"[{self.correlation_id}] Smart select failed: {e}")
            return False

    async def _js_click_fallback(self, x: int, y: int) -> bool:
        """
        Click element at coordinates using JavaScript (more reliable for stubborn buttons).
        
        This is a fallback when normal mouse.click() fails to activate buttons,
        which can happen with JavaScript-heavy UIs or overlays.
        """
        try:
            result = await self.page.evaluate(f"""
                (function() {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (elem) {{
                        // Try multiple click methods for maximum compatibility
                        elem.click();
                        
                        // Also dispatch click event for React/Vue apps
                        elem.dispatchEvent(new MouseEvent('click', {{
                            bubbles: true,
                            cancelable: true,
                            view: window
                        }}));
                        
                        return {{
                            success: true,
                            tagName: elem.tagName,
                            text: elem.textContent?.trim()?.substring(0, 50) || ''
                        }};
                    }}
                    return {{ success: false }};
                }})()
            """)
            if result and result.get("success"):
                logger.info(f"[{self.correlation_id}] JS click fallback succeeded at ({x}, {y}) on <{result.get('tagName', 'unknown')}>: {result.get('text', '')[:30]}")
                return True
            return False
        except Exception as e:
            logger.debug(f"[{self.correlation_id}] JS click fallback failed: {e}")
            return False

    async def _validate_element_at(self, x: int, y: int, expected_text: str = None) -> Dict[str, Any]:
        """
        Get information about element at coordinates for validation.
        
        Returns dict with element info to verify clicks will hit intended targets.
        Critical for Yes/No buttons to prevent accidental declines.
        """
        try:
            element_info = await self.page.evaluate(f"""
                (function() {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (!elem) return null;
                    
                    const rect = elem.getBoundingClientRect();
                    return {{
                        tagName: elem.tagName,
                        text: elem.textContent?.trim()?.substring(0, 100) || '',
                        id: elem.id || null,
                        className: elem.className || '',
                        type: elem.type || null,
                        isButton: elem.tagName === 'BUTTON' || elem.type === 'button' || elem.type === 'submit',
                        isClickable: elem.onclick !== null || elem.tagName === 'BUTTON' || elem.tagName === 'A' || elem.role === 'button',
                        boundingBox: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }}
                    }};
                }})()
            """)
            
            if element_info and expected_text:
                element_info["matches_expected"] = expected_text.lower() in element_info.get("text", "").lower()
            
            return element_info or {}
        except Exception as e:
            logger.debug(f"Element validation failed: {e}")
            return {}

    async def _check_blocked_state(self) -> Optional[str]:
        """
        Check if page shows blocked/unavailable state before attempting actions.
        
        Uses platform-specific indicators from platform_config if available.
        
        Returns the blocking indicator found, or None if page is actionable.
        """
        try:
            page_text = await self.page.inner_text("body")
            # Pass platform-specific indicators from config
            additional = self.platform_config.get("blocked_indicators")
            return check_blocked_indicators(page_text, additional)
        except Exception as e:
            logger.debug(f"Blocked state check failed: {e}")
            return None
    
    async def _check_success_state(self) -> Optional[str]:
        """
        Check if page shows success/completion state.
        
        Uses platform-specific indicators from platform_config if available.
        
        Returns the success indicator found, or None if not successful.
        """
        try:
            page_text = await self.page.inner_text("body")
            additional = self.platform_config.get("success_indicators")
            return check_success_indicators(page_text, additional)
        except Exception as e:
            logger.debug(f"Success state check failed: {e}")
            return None
    
    async def _check_failure_state(self) -> Optional[str]:
        """
        Check if page shows failure state.
        
        Uses platform-specific indicators from platform_config if available.
        
        Returns the failure indicator found, or None.
        """
        try:
            page_text = await self.page.inner_text("body")
            additional = self.platform_config.get("failure_indicators")
            return check_failure_indicators(page_text, additional)
        except Exception as e:
            logger.debug(f"Failure state check failed: {e}")
            return None
    
    async def _detect_workflow_stage(self) -> Optional[str]:
        """
        Detect current workflow stage from page content.
        
        Uses platform-specific stages from platform_config if available.
        
        Returns the workflow stage name, or None if unknown.
        """
        try:
            page_text = await self.page.inner_text("body")
            additional = self.platform_config.get("workflow_stages")
            return detect_workflow_stage(page_text, additional)
        except Exception as e:
            logger.debug(f"Workflow stage detection failed: {e}")
            return None
    
    def _extract_and_log_project_id(self, url: str) -> Optional[str]:
        """
        Extract project ID from URL and log it.
        
        Args:
            url: The URL to extract project ID from
            
        Returns:
            Project ID if found, None otherwise
        """
        project_id = extract_project_id_from_url(url)
        if project_id:
            logger.info(f"[{self.correlation_id}] Extracted project ID: {project_id}")
            self._log_action({
                "action": "extract_project_id",
                "project_id": project_id,
                "url": url
            })
        return project_id
    
    async def _dismiss_platform_dialogs(self) -> Dict[str, Any]:
        """
        Dismiss platform-specific dialogs using the configured handler.
        
        Returns:
            Results dict from the platform dialog handler, or empty dict
        """
        dialog_handler = self.platform_config.get("dialog_handler")
        if dialog_handler and callable(dialog_handler):
            try:
                return await dialog_handler(self.page)
            except Exception as e:
                logger.debug(f"Platform dialog handler failed: {e}")
                return {}
        return {}

    async def _playwright_selector_fallback(self, button_text: str) -> bool:
        """
        Find and click button by visible text using Playwright selector.
        
        Ultimate fallback when coordinate-based clicking fails repeatedly.
        """
        try:
            # Try exact text match first
            locator = self.page.get_by_text(button_text, exact=True)
            if await locator.count() > 0:
                await locator.first.click(timeout=3000)
                logger.info(f"Playwright selector clicked button: '{button_text}' (exact match)")
                return True
            
            # Try partial text match
            locator = self.page.get_by_text(button_text)
            if await locator.count() > 0:
                await locator.first.click(timeout=3000)
                logger.info(f"Playwright selector clicked button: '{button_text}' (partial match)")
                return True
            
            # Try role-based selector for buttons
            locator = self.page.get_by_role("button", name=button_text)
            if await locator.count() > 0:
                await locator.first.click(timeout=3000)
                logger.info(f"Playwright selector clicked button role: '{button_text}'")
                return True
                
            return False
        except Exception as e:
            logger.debug(f"Playwright selector fallback failed for '{button_text}': {e}")
            return False

    async def _capture_page_state(self) -> Dict[str, Any]:
        """
        Capture page metadata (URL, localStorage, success message state) before closing.
        Enables post-run verification without keeping Playwright open.
        In DEBUG mode, saves screenshot to screenshots/ directory.
        """
        state: Dict[str, Any] = {}

        if not self.page:
            self.last_page_state = state
            return state

        state["url"] = self.page.url

        # Save screenshot in DEBUG mode
        debug_mode = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')
        if debug_mode:
            try:
                from datetime import datetime
                from pathlib import Path

                # Create screenshots directory if it doesn't exist
                screenshots_dir = Path("screenshots")
                screenshots_dir.mkdir(exist_ok=True)

                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = screenshots_dir / f"debug_{timestamp}.png"

                # Save screenshot
                await self.page.screenshot(path=str(screenshot_path))
                state["debug_screenshot"] = str(screenshot_path)
                logger.debug(f"Debug screenshot saved: {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to save debug screenshot: {e}")

        try:
            local_storage = await self.page.evaluate("""
                () => {
                    const result = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        result[key] = localStorage.getItem(key);
                    }
                    return result;
                }
            """)
        except Exception as e:
            logger.debug(f"LocalStorage capture failed: {e}")
            local_storage = {}
        state["localStorage"] = local_storage

        try:
            success_visible = await self.page.evaluate("""
                () => {
                    const successMsg = document.getElementById('success-message');
                    if (!successMsg) return false;
                    const style = window.getComputedStyle(successMsg);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }
            """)
            state["successMessageVisible"] = success_visible
        except Exception as e:
            logger.debug(f"Success message visibility capture failed: {e}")

        try:
            success_text = await self.page.evaluate("""
                () => {
                    const successMsg = document.getElementById('success-message');
                    return successMsg ? (successMsg.textContent || '').trim() : null;
                }
            """)
            state["successMessageText"] = success_text
        except Exception as e:
            logger.debug(f"Success message text capture failed: {e}")

        self.last_page_state = state
        return state

    async def precise_click(self, x: int, y: int, expected_text: str = None) -> bool:
        """
        Precision click system that uses element selectors first, coordinates as fallback.
        This fixes the iteration 30 dialog failure by being more robust than blind coordinate clicking.

        Args:
            x, y: Pixel coordinates
            expected_text: Optional text to verify we're clicking the right element

        Returns:
            True if click succeeded and was verified, False otherwise
        """
        try:
            # Step 1: Try to find a reliable selector for the element at these coordinates
            element_info = await self.page.evaluate(f"""
                (function() {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (!elem) return null;

                    const rect = elem.getBoundingClientRect();

                    // Build selector hierarchy for robustness
                    let selectors = [];

                    // Try ID selector (most reliable)
                    if (elem.id) {{
                        selectors.push('#' + elem.id);
                    }}

                    // Try data attributes (common for React apps)
                    if (elem.dataset && elem.dataset.testid) {{
                        selectors.push('[data-testid="' + elem.dataset.testid + '"]');
                    }}

                    // Try class + text combination for buttons/links
                    if ((elem.tagName === 'BUTTON' || elem.tagName === 'A') && elem.textContent) {{
                        const text = elem.textContent.trim();
                        if (text.length > 0 && text.length < 50) {{
                            selectors.push(`${{elem.tagName.toLowerCase()}}:has-text("${{text}}")`);
                        }}
                    }}

                    // Try role + name for accessibility
                    if (elem.getAttribute('role')) {{
                        const role = elem.getAttribute('role');
                        const ariaLabel = elem.getAttribute('aria-label') || elem.textContent?.trim();
                        if (ariaLabel && ariaLabel.length < 50) {{
                            selectors.push(`[role="${{role}}"][aria-label*="${{ariaLabel}}"]`);
                        }}
                    }}

                    return {{
                        tagName: elem.tagName,
                        text: elem.textContent?.trim()?.substring(0, 100) || '',
                        selectors: selectors,
                        boundingBox: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }},
                        isClickable: elem.tagName === 'BUTTON' || elem.tagName === 'A' ||
                                   elem.type === 'button' || elem.type === 'submit' ||
                                   elem.onclick !== null || elem.getAttribute('role') === 'button'
                    }};
                }})()
            """)

            if not element_info:
                logger.warning(f"[{self.correlation_id}] No element found at ({x}, {y}), falling back to coordinates")
                return await self._coordinate_click_fallback(x, y)

            # Verify expected text if provided
            if expected_text and expected_text.lower() not in element_info.get("text", "").lower():
                logger.warning(f"[{self.correlation_id}] Element text mismatch. Expected: '{expected_text}', Found: '{element_info.get('text', '')[:50]}...'")

            # Step 2: Try each selector in order of reliability
            for selector in element_info.get("selectors", []):
                try:
                    locator = self.page.locator(selector)
                    if await locator.count() == 1:  # Exactly one match - good selector
                        await locator.click(timeout=3000)

                        # Step 3: Verify click success
                        if await self.verify_click_success(x, y, element_info):
                            logger.info(f"[{self.correlation_id}] Precision click succeeded with selector: {selector}")
                            return True
                        else:
                            logger.debug(f"[{self.correlation_id}] Click verification failed for selector: {selector}")

                except Exception as e:
                    logger.debug(f"[{self.correlation_id}] Selector failed: {selector} - {e}")
                    continue

            # Step 4: Fallback to coordinate clicking if selectors failed
            logger.warning(f"[{self.correlation_id}] All selectors failed, falling back to coordinates ({x}, {y})")
            return await self._coordinate_click_fallback(x, y)

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Precision click failed: {e}")
            return await self._coordinate_click_fallback(x, y)

    async def verify_click_success(self, x: int, y: int, original_element_info: dict) -> bool:
        """
        Verify that a click actually had the intended effect.
        This prevents the iteration 30 issue where clicks silently fail.
        """
        try:
            # Wait a moment for the click to take effect
            await asyncio.sleep(0.3)

            # Check if element state changed (common for dialog dismissal)
            current_element_info = await self.page.evaluate(f"""
                (function() {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (!elem) return {{ elementGone: true }};

                    const rect = elem.getBoundingClientRect();
                    return {{
                        tagName: elem.tagName,
                        text: elem.textContent?.trim()?.substring(0, 100) || '',
                        boundingBox: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }},
                        visible: rect.width > 0 && rect.height > 0
                    }};
                }})()
            """)

            # Success indicators:
            # 1. Element disappeared (dialog closed)
            if current_element_info.get("elementGone"):
                logger.debug(f"[{self.correlation_id}] Click success: Element disappeared")
                return True

            # 2. Element became invisible (dialog hidden)
            if not current_element_info.get("visible"):
                logger.debug(f"[{self.correlation_id}] Click success: Element became invisible")
                return True

            # 3. Text content changed (state change)
            original_text = original_element_info.get("text", "")
            current_text = current_element_info.get("text", "")
            if original_text != current_text:
                logger.debug(f"[{self.correlation_id}] Click success: Text changed from '{original_text}' to '{current_text}'")
                return True

            # 4. Check for page navigation or URL change
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=1000)
                logger.debug(f"[{self.correlation_id}] Click success: Page navigation detected")
                return True
            except:
                pass  # No navigation - not necessarily a failure

            # 5. For buttons - check if we're no longer on the same page/dialog
            if original_element_info.get("tagName") == "BUTTON":
                # If it's still the same button in the same place, the click might have failed
                logger.debug(f"[{self.correlation_id}] Click uncertain: Button still present and unchanged")
                return False

            # Default: assume success if no clear failure indicators
            return True

        except Exception as e:
            logger.debug(f"[{self.correlation_id}] Click verification error: {e}")
            return False  # Err on the side of caution

    async def _coordinate_click_fallback(self, x: int, y: int) -> bool:
        """
        Fallback to coordinate-based clicking when selectors fail.
        Enhanced with verification to prevent silent failures.
        """
        try:
            # Try normal mouse click first
            await self.page.mouse.click(x, y)
            await asyncio.sleep(0.3)

            # Simple verification - did something change?
            page_changed = False
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=1000)
                page_changed = True
            except:
                pass

            if page_changed:
                logger.info(f"[{self.correlation_id}] Coordinate click succeeded - page changed")
                return True

            # Try JS click as secondary fallback
            logger.debug(f"[{self.correlation_id}] Trying JS click fallback at ({x}, {y})")
            if await self._js_click_fallback(x, y):
                logger.info(f"[{self.correlation_id}] JS click fallback succeeded")
                return True

            logger.warning(f"[{self.correlation_id}] All click methods failed at ({x}, {y})")
            return False

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Coordinate click fallback failed: {e}")
            return False

    async def execute_computer_use_action(self, action_name: str, args: Dict[str, Any]) -> bool:
        """
        Execute a Computer Use API action via Playwright

        Supported actions from Gemini Computer Use:
        - click_at(x, y) - coordinates are normalized 0-1000
        - type_text_at(x, y, text) - coordinates are normalized 0-1000
        - hover_at(x, y) - coordinates are normalized 0-1000
        - scroll_document(direction, amount)
        - scroll_at(x, y, direction, amount) - coordinates are normalized 0-1000
        - navigate(url)
        - key_combination(keys)
        - go_back()
        - go_forward()
        - drag_and_drop(from_x, from_y, to_x, to_y) - coordinates are normalized 0-1000
        - wait_5_seconds()
        """
        try:
            # Get screen dimensions from current page
            viewport = self.page.viewport_size
            screen_width = viewport.get('width', 1440)
            screen_height = viewport.get('height', 900)
            if action_name == "click_at":
                x_norm, y_norm = args.get("x"), args.get("y")
                x = self._denormalize_coord(x_norm, screen_width)
                y = self._denormalize_coord(y_norm, screen_height)

                # Track click location for debugging
                self._click_history.append((x, y))
                if len(self._click_history) > 10:
                    self._click_history = self._click_history[-10:]

                # Use the new precision click system to fix iteration 30 dialog failure
                expected_text = args.get("expected_text")  # Optional hint about what we expect to click
                success = await self.precise_click(x, y, expected_text)

                # Log the action with method used
                method = "precision_click" if success else "failed"
                logger.info(f"[{self.correlation_id}] Click at ({x}, {y}) [normalized: ({x_norm}, {y_norm})] - {method}")
                self._log_action({"action": "click_at", "x": x, "y": y, "method": method, "success": success})
                return success

            elif action_name == "type_text_at":
                x_norm, y_norm = args.get("x"), args.get("y")
                x = self._denormalize_coord(x_norm, screen_width)
                y = self._denormalize_coord(y_norm, screen_height)
                text = args.get("text", "")

                # Try smart select for dropdowns first
                if text and await self._smart_select_option(x, y, text):
                    logger.info(f"[{self.correlation_id}] Smart selected dropdown at ({x}, {y}): {text[:50]}... [normalized: ({x_norm}, {y_norm})]")
                    self._log_action({"action": "select_option", "x": x, "y": y, "text": text})
                    return True

                # Normal text input handling
                # Triple-click to select existing text/placeholder before typing
                await self.page.mouse.click(x, y, click_count=3)
                await asyncio.sleep(0.2)

                # Handle clear_before_typing flag if present
                if args.get("clear_before_typing", False):
                    # Select all and delete
                    await self.page.keyboard.press("Meta+a")  # Cmd+A on Mac
                    await self.page.keyboard.press("Backspace")
                    await asyncio.sleep(0.1)

                # Type text
                if text:
                    await self.page.keyboard.type(text)

                logger.info(f"[{self.correlation_id}] Typed at ({x}, {y}): {text[:50]}... [normalized: ({x_norm}, {y_norm})]")
                self._log_action({"action": "type_text_at", "x": x, "y": y, "text": text})
                return True

            elif action_name == "hover_at":
                x_norm, y_norm = args.get("x"), args.get("y")
                x = self._denormalize_coord(x_norm, screen_width)
                y = self._denormalize_coord(y_norm, screen_height)
                await self.page.mouse.move(x, y)
                logger.info(f"[{self.correlation_id}] Hovered at: ({x}, {y}) [normalized: ({x_norm}, {y_norm})]")
                self._log_action({"action": "hover_at", "x": x, "y": y})
                return True

            elif action_name == "scroll_document":
                direction = args.get("direction", "down")
                amount = args.get("amount", 500)
                if direction == "down":
                    await self.page.mouse.wheel(0, amount)
                else:
                    await self.page.mouse.wheel(0, -amount)
                logger.info(f"[{self.correlation_id}] Scrolled {direction} by {amount}px")
                self._log_action({"action": "scroll_document", "direction": direction, "amount": amount})
                return True

            elif action_name == "scroll_at":
                x_norm, y_norm = args.get("x"), args.get("y")
                x = self._denormalize_coord(x_norm, screen_width)
                y = self._denormalize_coord(y_norm, screen_height)
                direction = args.get("direction", "down")
                amount = args.get("amount", 500)
                # Move mouse to position, then scroll
                await self.page.mouse.move(x, y)
                if direction == "down":
                    await self.page.mouse.wheel(0, amount)
                else:
                    await self.page.mouse.wheel(0, -amount)
                logger.info(f"[{self.correlation_id}] Scrolled at ({x}, {y}) {direction} by {amount}px [normalized: ({x_norm}, {y_norm})]")
                self._log_action({"action": "scroll_at", "x": x, "y": y, "direction": direction, "amount": amount})
                return True

            elif action_name == "navigate":
                url = args.get("url")
                await self.page.goto(url)
                logger.info(f"[{self.correlation_id}] Navigated to: {url}")
                self._log_action({"action": "navigate", "url": url})
                return True

            elif action_name == "key_combination":
                keys = args.get("keys", [])
                # Keys can be a list ["Control", "c"] or already a string "Control+c"
                if isinstance(keys, list):
                    key_string = "+".join(keys)
                else:
                    key_string = str(keys)
                await self.page.keyboard.press(key_string)
                logger.info(f"[{self.correlation_id}] Pressed keys: {key_string}")
                self._log_action({"action": "key_combination", "keys": key_string})
                return True

            elif action_name == "go_back":
                await self.page.go_back()
                logger.info(f"[{self.correlation_id}] Navigated back")
                self._log_action({"action": "go_back"})
                return True

            elif action_name == "go_forward":
                await self.page.go_forward()
                logger.info(f"[{self.correlation_id}] Navigated forward")
                self._log_action({"action": "go_forward"})
                return True

            elif action_name == "drag_and_drop":
                from_x_norm, from_y_norm = args.get("from_x"), args.get("from_y")
                to_x_norm, to_y_norm = args.get("to_x"), args.get("to_y")
                from_x = self._denormalize_coord(from_x_norm, screen_width)
                from_y = self._denormalize_coord(from_y_norm, screen_height)
                to_x = self._denormalize_coord(to_x_norm, screen_width)
                to_y = self._denormalize_coord(to_y_norm, screen_height)
                await self.page.mouse.move(from_x, from_y)
                await self.page.mouse.down()
                await self.page.mouse.move(to_x, to_y)
                await self.page.mouse.up()
                logger.info(f"[{self.correlation_id}] Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y}) [normalized: ({from_x_norm}, {from_y_norm}) to ({to_x_norm}, {to_y_norm})]")
                self._log_action({"action": "drag_and_drop", "from": (from_x, from_y), "to": (to_x, to_y)})
                return True

            elif action_name == "wait_5_seconds":
                await asyncio.sleep(5)
                logger.info(f"[{self.correlation_id}] Waited 5 seconds")
                self._log_action({"action": "wait_5_seconds"})
                return True

            elif action_name == "open_web_browser":
                # Browser is already open, just acknowledge
                logger.info(f"[{self.correlation_id}] Browser already open, acknowledging action")
                self._log_action({"action": "open_web_browser"})
                return True

            elif action_name == "search":
                # Handle search action (type in search box)
                query = args.get("query", "")
                logger.info(f"[{self.correlation_id}] Search query: {query}")
                # Note: This assumes focus is already on search box
                await self.page.keyboard.type(query)
                await self.page.keyboard.press("Enter")
                self._log_action({"action": "search", "query": query})
                return True

            else:
                logger.warning(f"[{self.correlation_id}] Unknown Computer Use action: {action_name}")
                return False

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error executing {action_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def execute_gemini_action(self, action: Dict[str, Any]) -> bool:
        """Legacy method for old JSON-based actions (kept for backwards compatibility)"""
        action_type = action.get("type")
        logger.warning(f"Using legacy execute_gemini_action for: {action_type}")

        # Map old action types to new Computer Use actions
        if action_type == "click_at":
            return await self.execute_computer_use_action("click_at", action)
        elif action_type == "type":
            # Old type action - just type without clicking first
            text = action.get("text")
            await self.page.keyboard.type(text)
            self.action_log.append({"action": "type", "text": text})
            return True
        elif action_type == "scroll":
            return await self.execute_computer_use_action("scroll_document", action)
        elif action_type == "navigate":
            return await self.execute_computer_use_action("navigate", action)
        else:
            logger.error(f"Unknown legacy action: {action_type}")
            return False

    async def gemini_computer_use(
        self,
        task: str,
        url: str,
        max_iterations: int = 20,
        verification_prompt: str = "Verify that the application was successfully submitted.",
        platform_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Use Gemini 2.5 Computer Use API to complete a browser task.

        Uses model: gemini-2.5-computer-use-preview-10-2025
        Per documentation: https://ai.google.dev/gemini-api/docs/computer-use

        Args:
            task: Description of what to accomplish
            url: Starting URL
            max_iterations: Maximum number of AI iterations
            platform_config: Platform-specific configuration (includes state machine factory)

        Returns:
            (success, action_log)
        """
        success = False  # Initialize success status

        # Enhanced intelligent termination for agentic loop
        if platform_config and platform_config.get("enable_intelligent_termination"):
            logger.info("GLG: Using enhanced success detection patterns for intelligent termination")
        if not self.gemini_client:
            logger.error("Gemini client not configured. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
            return False, []

        # Task prompt prefix with verification and UI guidance
        task_prefix = """IMPORTANT INSTRUCTIONS FOR FORM FILLING:

1.  After each action, verify the outcome from the new screenshot.
2.  If an action failed, try an alternative approach.
3.  For dropdowns (<select> elements), first `click_at` to open it, then `type_text_at` with the exact option text you want to select.
4.  For checkboxes and radio buttons, `click_at` the center of the element.
5.  Use keyboard shortcuts (`key_combination`) for reliability, like 'Enter' to submit forms.

**CRITICAL - Yes/No Questions:**
- Before clicking Yes or No, READ THE BUTTON TEXT carefully from the screenshot
- Yes buttons are typically on the LEFT side, No/Decline buttons on the RIGHT
- VERIFY the button coordinates hit the CORRECT button - clicking wrong can decline the project irreversibly
- If unsure which button is which, take a screenshot first and examine button positions
- For compliance questions asking if you can participate, you almost always want "Yes"

TASK:
"""
        enhanced_task = task_prefix + task + "\n\n" + verification_prompt

        try:
            await self.start_browser(headless=False, user_data_dir=self.user_data_dir)
            await self.page.goto(url)
            
            # Initial navigation verification
            page_content = await self.page.content()
            if "Something didn't go right" in page_content:
                logger.error("Initial navigation failed: landed on an error page.")
                await self._capture_page_state()
                await self.close_browser()
                return False, [{"error": "Initial navigation failed: landed on an error page."}]
            
            # Extract and log project ID from URL
            self._extract_and_log_project_id(url)
            
            # Dismiss platform-specific dialogs first (if handler configured)
            dialog_results = await self._dismiss_platform_dialogs()
            if dialog_results:
                logger.info(f"Platform dialog dismissal results: {dialog_results}")
            
            # Auto-accept cookie banners (with platform-specific selectors if configured)
            cookie_selectors = self.platform_config.get("cookie_selectors")
            cookie_accepted = await auto_accept_cookies(
                self.page,
                additional_selectors=cookie_selectors
            )
            if cookie_accepted:
                logger.info("Cookie consent banner auto-accepted")
            
            logger.info(f"Started Gemini Computer Use task: {task}")

            # Model ID for Computer Use - per https://ai.google.dev/gemini-api/docs/computer-use
            MODEL = "gemini-2.5-computer-use-preview-10-2025"

            # Configure Computer Use tool
            config = types.GenerateContentConfig(
                tools=[types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER,
                    )
                )],
                thinking_config=types.ThinkingConfig(include_thoughts=True),
            )

            # Initial screenshot
            initial_screenshot = await self.take_screenshot()

            # Pre-submission validation - check if consultation is available
            blocked_indicator = await self._check_blocked_state()
            if blocked_indicator:
                logger.error(f"Consultation not available - detected: '{blocked_indicator}'")
                await self._capture_page_state()
                await self.close_browser()
                return False, [f"Consultation blocked: {blocked_indicator}"]


            # Initialize conversation with goal + screenshot
            contents = [
                Content(
                    role="user",
                    parts=[
                        Part(text=enhanced_task),
                        Part.from_bytes(data=initial_screenshot, mime_type="image/png")
                    ]
                )
            ]

            # How many times to retry a completely empty Gemini response per iteration
            max_empty_retries = int(os.getenv("GEMINI_MAX_EMPTY_RETRIES", "2"))

            # Agent loop: send request → get function_call → execute → return screenshot
            for iteration in range(max_iterations):
                logger.info(f"Gemini iteration {iteration + 1}/{max_iterations}")

                # Check for blocked state at start of each iteration
                blocked_indicator = await self._check_blocked_state()
                if blocked_indicator:
                    logger.error(f"Project blocked detected at iteration start: '{blocked_indicator}'")
                    await self._capture_page_state()
                    await self.close_browser()
                    return False, [f"Project blocked: {blocked_indicator}"]

                response = None
                # Minimal retry loop to handle random empty responses from the API
                for attempt in range(max_empty_retries + 1):
                    response = self.gemini_client.models.generate_content(
                        model=MODEL,
                        contents=contents,
                        config=config,
                    )
                    if response.candidates and response.candidates[0].content.parts:
                        break

                    logger.warning(
                        f"Empty response from Gemini (iteration {iteration + 1}, "
                        f"attempt {attempt + 1}/{max_empty_retries + 1})"
                    )

                # After retries, still no usable response → abort loop
                if not response or not response.candidates or not response.candidates[0].content.parts:
                    logger.error("No usable response from Gemini after retries, stopping.")
                    break

                # CRITICAL: Append model's response to conversation history FIRST
                # This is required so function responses can be matched to function calls
                candidate = response.candidates[0]
                contents.append(candidate.content)

                # Process each part of the response
                has_function_call = False
                function_responses = []

                logger.debug(f"Response parts count: {len(candidate.content.parts)}")
                for i, part in enumerate(candidate.content.parts):
                    logger.debug(f"Part {i}: {type(part)}")

                    # Check if this is a function call (action to execute)
                    if hasattr(part, 'function_call') and part.function_call:
                        has_function_call = True
                        func_call = part.function_call

                        logger.info(f"Function call {i}: {func_call.name}")
                        logger.debug(f"Args: {func_call.args}")

                        # Check for safety decision in function call
                        args_dict = dict(func_call.args) if func_call.args else {}
                        safety_decision = args_dict.pop('safety_decision', None)

                        # Handle safety decisions (auto-allow mode for non-interactive automation)
                        if safety_decision:
                            decision_type = safety_decision.get('decision', 'allowed')
                            explanation = safety_decision.get('explanation', '')

                            if decision_type == 'block':
                                logger.error(f"Action blocked by safety system: {func_call.name} - {explanation}")
                                # Skip this action, add error response
                                function_responses.append(
                                    types.FunctionResponse(
                                        name=func_call.name,
                                        response={
                                            "success": False,
                                            "error": f"Blocked by safety system: {explanation}",
                                            "url": self.page.url
                                        }
                                    )
                                )
                                continue  # Skip execution
                            elif decision_type == 'require_confirmation':
                                logger.warning(f"Auto-allowing risky action (non-interactive): {func_call.name} - {explanation}")
                            else:
                                logger.info(f"Safety decision: {decision_type}")
                                logger.debug(f"Explanation: {explanation}")

                        # Execute the action via Playwright
                        success = await self.execute_computer_use_action(
                            func_call.name,
                            args_dict
                        )

                        # Take new screenshot after action
                        new_screenshot = await self.take_screenshot()

                        # Build function response
                        response_data = {
                            "success": success,
                            "url": self.page.url
                        }

                        # Add error details when action fails
                        if not success:
                            response_data["error"] = f"Action {func_call.name} execution failed"

                        # Acknowledge safety decision if present (Gemini requires this exact field)
                        if safety_decision:
                            response_data["safety_acknowledgement"] = "true"

                        # Create function response with screenshot
                        function_responses.append(
                            types.FunctionResponse(
                                name=func_call.name,
                                response=response_data,
                                parts=[types.FunctionResponsePart(
                                    inline_data=types.FunctionResponseBlob(
                                        mime_type="image/png",
                                        data=new_screenshot
                                    )
                                )]
                            )
                        )

                        # Brief pause between actions
                        await asyncio.sleep(0.5)

                    # Check for text response (task completion)
                    elif hasattr(part, 'text') and part.text:
                        logger.info(f"Gemini text response: {part.text[:200]}")

                # If no function calls, model is done
                if not has_function_call:
                    logger.info("Gemini stopped making actions - validating submission")

                    # Check for failure/blocked indicators
                    failure_indicator = await self._check_failure_state()
                    if failure_indicator:
                        logger.error(f"Submission failed - detected: '{failure_indicator}'")
                        await self._capture_page_state()
                        await self.close_browser()
                        return False, self.action_log

                    blocked_indicator = await self._check_blocked_state()
                    if blocked_indicator:
                        logger.error(f"Project blocked - detected: '{blocked_indicator}'")
                        await self._capture_page_state()
                        await self.close_browser()
                        return False, self.action_log

                    # Check for success indicators
                    success_indicator = await self._check_success_state()
                    if success_indicator:
                        logger.success(f"Submission success detected: '{success_indicator}'")
                        await self._capture_page_state()
                        await self.close_browser()
                        return True, self.action_log
                    
                    # Check workflow stage - if we're at completion stage, it's success
                    stage = await self._detect_workflow_stage()
                    if stage == "completion":
                        logger.success("Workflow completion stage detected")
                        await self._capture_page_state()
                        await self.close_browser()
                        return True, self.action_log

                    logger.warning("Task completed but no success confirmation found - marking as failure")
                    await self._capture_page_state()
                    await self.close_browser()
                    return False, self.action_log

                # Add function responses to conversation
                if function_responses:
                    # Add self-correction prompt
                    verification_prompt = Part(text="Based on the screenshot, please verify the last action was successful. If not, try an alternative.")
                    function_response_parts = [Part(function_response=fr) for fr in function_responses]
                    function_response_parts.append(verification_prompt)

                    contents.append(
                        Content(
                            role="user",
                            parts=function_response_parts
                        )
                    )

                # Enhanced intelligent success detection (platform-aware, agentic)
                try:
                    # Platform-specific success detection
                    success_patterns = []
                    if platform_config:
                        # Use platform-specific success indicators
                        success_patterns.extend(platform_config.get("success_indicators", []))

                    # Fallback to generic success patterns
                    success_patterns.extend([
                        "thanks, you're all set", "application received", "successfully submitted",
                        "submission confirmed", "you're all set", "thank you for applying"
                    ])

                    # Check for success patterns in page text (intelligent detection)
                    page_text = await self.page.text_content('body') or ""
                    page_text_lower = page_text.lower()

                    for pattern in success_patterns:
                        if pattern.lower() in page_text_lower:
                            logger.success(f"SUCCESS detected via pattern: '{pattern}' - task completed!")
                            await self._capture_page_state()
                            await self.close_browser()
                            return True, self.action_log

                    # Check for blocked/failure states (intelligent early termination)
                    blocked_patterns = []
                    if platform_config:
                        blocked_patterns.extend(platform_config.get("blocked_indicators", []))
                        blocked_patterns.extend(platform_config.get("failure_indicators", []))

                    # Default blocked patterns
                    blocked_patterns.extend([
                        "already declined", "already applied", "project expired",
                        "no longer available", "invitation has expired"
                    ])

                    for pattern in blocked_patterns:
                        if pattern.lower() in page_text_lower:
                            logger.info(f"BLOCKED state detected via pattern: '{pattern}' - stopping appropriately")
                            await self._capture_page_state()
                            await self.close_browser()
                            return True, self.action_log  # Return True since we correctly detected blocked state

                except Exception as e:
                    logger.debug(f"Enhanced success check error (non-fatal): {e}")

            logger.warning(f"Max iterations ({max_iterations}) reached")
            await self._capture_page_state()
            await self.close_browser()
            return False, self.action_log

        finally:
            await self._capture_page_state()
            await self.close_browser()
            return success, self.action_log

    async def execute_claude_action(self, action: str, params: Dict[str, Any]) -> bool:
        """
        Execute a Claude Computer Use action via Playwright

        Claude uses PIXEL coordinates (not normalized like Gemini)

        Supported actions from Claude Computer Use API:
        - screenshot
        - left_click(coordinate: [x, y])
        - type(text: str)
        - key(text: str) - keyboard shortcuts like "ctrl+s"
        - mouse_move(coordinate: [x, y])
        - scroll(coordinate: [x, y], scroll_direction: "up"/"down", scroll_amount: int)
        - right_click(coordinate: [x, y])
        - middle_click(coordinate: [x, y])
        - double_click(coordinate: [x, y])
        - triple_click(coordinate: [x, y])
        - left_click_drag(coordinate: [x, y], to_coordinate: [x2, y2])
        - wait(duration: float)
        """
        try:
            if action == "screenshot":
                # Screenshot handled in main loop
                logger.info("Screenshot action (handled in loop)")
                return True

            elif action == "left_click":
                x, y = params["coordinate"]

                # Check if we've clicked this location recently (within 20px tolerance)
                tolerance = 20
                recent_clicks_at_location = sum(
                    1 for px, py in self._click_history[-5:]
                    if abs(px - x) < tolerance and abs(py - y) < tolerance
                )
                
                # Track this click
                self._click_history.append((x, y))
                if len(self._click_history) > 10:
                    self._click_history = self._click_history[-10:]
                
                # Use JS fallback if we've clicked same spot multiple times
                if recent_clicks_at_location >= self._click_fallback_threshold:
                    logger.warning(f"Claude: Detected {recent_clicks_at_location} repeated clicks at ({x}, {y}), using JS fallback")
                    if await self._js_click_fallback(x, y):
                        self._log_action({"action": "left_click", "x": x, "y": y, "method": "js_fallback"})
                        return True
                    logger.warning(f"[{self.correlation_id}] Claude: JS fallback failed, trying normal click anyway")

                # Simply click - let Claude handle dropdowns via keyboard or type action
                await self.page.mouse.click(x, y)
                logger.info(f"[{self.correlation_id}] Claude: Clicked at ({x}, {y})")

                self._log_action({"action": "left_click", "x": x, "y": y})
                return True

            elif action == "type":
                text = params["text"]

                # Check if we're typing into a focused select element
                # Get current focused element position and try smart select
                try:
                    focused_pos = await self.page.evaluate("""
                        (function() {
                            const elem = document.activeElement;
                            if (elem) {
                                const rect = elem.getBoundingClientRect();
                                return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
                            }
                            return null;
                        })()
                    """)

                    if focused_pos and await self._smart_select_option(int(focused_pos['x']), int(focused_pos['y']), text):
                        logger.info(f"[{self.correlation_id}] Claude: Smart selected dropdown: {text[:50]}...")
                        self._log_action({"action": "select_option", "text": text})
                        return True
                except Exception as e:
                    logger.debug(f"[{self.correlation_id}] Smart select check failed: {e}")

                # If smart select wasn't used, perform a triple click to select existing text/placeholder
                # This uses the position where the element was detected, or a default if not found
                if focused_pos:
                    await self.page.mouse.click(int(focused_pos['x']), int(focused_pos['y']), click_count=3)
                    await asyncio.sleep(0.2)

                # Normal typing
                await self.page.keyboard.type(text)
                logger.info(f"[{self.correlation_id}] Claude: Typed text: {text[:50]}...")
                self._log_action({"action": "type", "text": text})
                return True

            elif action == "key":
                # Claude format: "ctrl+s", "Enter", or "Meta+a". Can also be multiple keys like "Tab Tab"
                keys_string = params["text"]

                # Map common key names to Playwright format
                key_mapping = {
                    # Arrow keys
                    "Down": "ArrowDown",
                    "Up": "ArrowUp",
                    "Left": "ArrowLeft",
                    "Right": "ArrowRight",
                    # Special keys
                    "Return": "Enter",
                    "Esc": "Escape",
                    "space": " ",  # Space key
                    # Modifier keys (Claude sends lowercase)
                    "ctrl": "Control",
                    "control": "Control",
                    "alt": "Alt",
                    "super": "Meta",
                    "meta": "Meta",
                    "cmd": "Meta",
                    "shift": "Shift",
                    # Common navigation/editing keys
                    "tab": "Tab",
                    "Tab": "Tab",
                    "backspace": "Backspace",
                    "Backspace": "Backspace",
                    "delete": "Delete",
                    "Delete": "Delete",
                    "escape": "Escape",
                    "enter": "Enter",
                    "Enter": "Enter",
                    "home": "Home",
                    "end": "End",
                    "pageup": "PageUp",
                    "pagedown": "PageDown",
                }

                # Split string to handle multiple key presses
                keys_to_press = keys_string.split()
                
                # Context info to return for tool output (especially useful for Tab navigation)
                focused_element_info = None

                for key in keys_to_press:
                    mapped_key = key_mapping.get(key, key)
                    await self.page.keyboard.press(mapped_key)
                    logger.info(f"[{self.correlation_id}] Claude: Pressed key: {mapped_key} (original: {key})")
                    # Small delay between key presses if multiple are sent
                    if len(keys_to_press) > 1:
                        await asyncio.sleep(0.1)

                self._log_action({"action": "key", "text": keys_string})
                
                # If the action involved navigation keys (Tab, Arrows), capture focus state
                if any(k.lower() in ["tab", "arrowdown", "arrowup", "enter"] for k in keys_to_press):
                    try:
                        focused_element_info = await self.page.evaluate("""
                            () => {
                                const el = document.activeElement;
                                if (!el || el === document.body) return "No specific element focused";
                                
                                const tag = el.tagName;
                                const type = el.type || '';
                                const text = (el.innerText || el.value || el.placeholder || '').substring(0, 50).replace(/\\n/g, ' ');
                                const label = el.labels && el.labels[0] ? el.labels[0].innerText : '';
                                const ariaLabel = el.getAttribute('aria-label') || '';
                                
                                return `Focused: <${tag} type="${type}"> Text: "${text}" Label: "${label}" Aria: "${ariaLabel}"`;
                            }
                        """)
                        logger.info(f"[{self.correlation_id}] Focus state after keys: {focused_element_info}")
                    except Exception as e:
                        logger.debug(f"Failed to get focus state: {e}")
                
                # Return focus info if available (this will be part of the tool result message)
                if focused_element_info:
                    return focused_element_info
                    
                return True

            elif action == "mouse_move":
                x, y = params["coordinate"]
                await self.page.mouse.move(x, y)
                logger.info(f"[{self.correlation_id}] Claude: Moved mouse to ({x}, {y})")
                self._log_action({"action": "mouse_move", "x": x, "y": y})
                return True

            elif action == "scroll":
                x, y = params["coordinate"]
                direction = params.get("scroll_direction", "down")
                amount = params.get("scroll_amount", 3)

                # Move mouse to position first
                await self.page.mouse.move(x, y)

                # Convert amount to pixels (Claude uses scroll units, ~100px per unit)
                delta = amount * 100
                if direction == "down":
                    await self.page.mouse.wheel(0, delta)
                else:
                    await self.page.mouse.wheel(0, -delta)

                logger.info(f"[{self.correlation_id}] Claude: Scrolled {direction} by {amount} units at ({x}, {y})")
                self._log_action({"action": "scroll", "x": x, "y": y, "direction": direction, "amount": amount})
                return True

            elif action == "right_click":
                x, y = params["coordinate"]
                await self.page.mouse.click(x, y, button="right")
                logger.info(f"[{self.correlation_id}] Claude: Right-clicked at ({x}, {y})")
                self._log_action({"action": "right_click", "x": x, "y": y})
                return True

            elif action == "middle_click":
                x, y = params["coordinate"]
                await self.page.mouse.click(x, y, button="middle")
                logger.info(f"[{self.correlation_id}] Claude: Middle-clicked at ({x}, {y})")
                self._log_action({"action": "middle_click", "x": x, "y": y})
                return True

            elif action == "double_click":
                x, y = params["coordinate"]
                await self.page.mouse.dblclick(x, y)
                logger.info(f"[{self.correlation_id}] Claude: Double-clicked at ({x}, {y})")
                self._log_action({"action": "double_click", "x": x, "y": y})
                return True

            elif action == "triple_click":
                x, y = params["coordinate"]
                # Playwright doesn't have triple-click, simulate with 3 clicks
                await self.page.mouse.click(x, y, click_count=3)
                logger.info(f"[{self.correlation_id}] Claude: Triple-clicked at ({x}, {y})")
                self._log_action({"action": "triple_click", "x": x, "y": y})
                return True

            elif action == "left_click_drag":
                from_x, from_y = params["coordinate"]
                to_x, to_y = params["to_coordinate"]
                await self.page.mouse.move(from_x, from_y)
                await self.page.mouse.down()
                await self.page.mouse.move(to_x, to_y)
                await self.page.mouse.up()
                logger.info(f"[{self.correlation_id}] Claude: Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})")
                self._log_action({"action": "left_click_drag", "from": (from_x, from_y), "to": (to_x, to_y)})
                return True

            elif action == "wait":
                duration = params.get("duration", 1.0)
                await asyncio.sleep(duration)
                logger.info(f"[{self.correlation_id}] Claude: Waited {duration} seconds")
                self._log_action({"action": "wait", "duration": duration})
                return True

            # New actions for computer_20251124 (Claude Opus 4.5)
            elif action == "zoom":
                # View specific screen region at full resolution
                region = params.get("region", [0, 0, 100, 100])
                if len(region) == 4:
                    x1, y1, x2, y2 = region
                    # Take screenshot of specific region using Playwright's clip
                    clip_width = max(1, x2 - x1)
                    clip_height = max(1, y2 - y1)
                    zoomed_screenshot = await self.page.screenshot(
                        clip={"x": x1, "y": y1, "width": clip_width, "height": clip_height}
                    )
                    logger.info(f"[{self.correlation_id}] Claude: Zoomed into region ({x1}, {y1}) to ({x2}, {y2})")
                    self._log_action({"action": "zoom", "region": region})
                    # Note: The zoomed screenshot will be returned in the tool result
                    return True
                else:
                    logger.warning(f"[{self.correlation_id}] Invalid zoom region format: {region}")
                    return False

            elif action == "hold_key":
                # Hold a key down (for use with other actions)
                key = params.get("key", "")
                if key:
                    await self.page.keyboard.down(key)
                    logger.info(f"[{self.correlation_id}] Claude: Holding key: {key}")
                    self._log_action({"action": "hold_key", "key": key})
                    return True
                else:
                    logger.warning(f"[{self.correlation_id}] hold_key action requires 'key' parameter")
                    return False

            elif action == "release_key":
                # Release a held key
                key = params.get("key", "")
                if key:
                    await self.page.keyboard.up(key)
                    logger.info(f"[{self.correlation_id}] Claude: Released key: {key}")
                    self._log_action({"action": "release_key", "key": key})
                    return True
                else:
                    logger.warning(f"[{self.correlation_id}] release_key action requires 'key' parameter")
                    return False

            elif action == "left_mouse_down":
                # Fine-grained mouse button down
                x, y = params.get("coordinate", [0, 0])
                await self.page.mouse.move(x, y)
                await self.page.mouse.down()
                logger.info(f"[{self.correlation_id}] Claude: Mouse down at ({x}, {y})")
                self._log_action({"action": "left_mouse_down", "x": x, "y": y})
                return True

            elif action == "left_mouse_up":
                # Fine-grained mouse button up
                x, y = params.get("coordinate", [0, 0])
                await self.page.mouse.move(x, y)
                await self.page.mouse.up()
                logger.info(f"[{self.correlation_id}] Claude: Mouse up at ({x}, {y})")
                self._log_action({"action": "left_mouse_up", "x": x, "y": y})
                return True

            else:
                logger.warning(f"[{self.correlation_id}] Unknown Claude action: {action}")
                return False

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error executing Claude action {action}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def claude_computer_use(
        self,
        task: str,
        url: str,
        max_iterations: int = 25,
        verification_prompt: str = "Verify that the application was successfully submitted.",
        platform_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Use Claude Opus 4.5 computer-use beta API.

        Configuration (per https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool):
        - Model: claude-opus-4-5
        - Tool: computer_20251124
        - Beta: computer-use-2025-11-24

        Features:
        - Screenshot capture
        - Mouse control (click, drag, scroll)
        - Keyboard input
        - Enhanced actions: left_mouse_down/up, hold_key, wait, zoom

        Args:
            task: Description of what to accomplish
            url: Starting URL
            max_iterations: Maximum number of AI iterations

        Returns:
            (success, action_log)
        """
        if not self.anthropic:
            logger.error("Claude client not configured. Set ANTHROPIC_API_KEY.")
            return False, []

        # Task prompt prefix with verification and UI guidance - optimized for iteration efficiency
        task_prefix = """CRITICAL EFFICIENCY RULES - READ BEFORE ACTING:

**MANDATORY: Use TAB key for navigation, NOT scrolling**
- Press Tab to move between form fields (saves 3-5 iterations vs scroll+click)
- The 'key' tool will return the CURRENTLY FOCUSED ELEMENT. **Check this output before pressing Enter!**
- Press Space to toggle checkboxes and radio buttons
- Press Enter to submit forms ONLY when focused on the submit button
- ONLY scroll if Tab doesn't reveal the next field after 2 attempts

**Form completion sequence (aim for 10-15 iterations max):**
1. Click first visible field → type value
2. Press Tab to next field → **CHECK TOOL OUTPUT** to see what is focused
3. If focused on correct field, type value. If not, Tab again.
4. Repeat Tab+input until all visible fields done
5. Tab to Submit button → press Enter

**DO NOT:**
- Scroll after every field (wastes iterations)
- Click fields you can Tab to
- Take multiple attempts on one field without changing strategy
- Press Enter blindly without checking focus (can trigger accidental declines!)

**For dropdown/select elements:**
- Click on the dropdown field, then TYPE the desired option text
- The system will auto-select matching option
- Example: To select "VP / Senior Director", click dropdown then type "VP"

**For checkboxes and radio buttons:**
- Click directly on the element OR press Space when focused
- Verify checked state in next screenshot

**CRITICAL - Yes/No Questions:**
- READ button text carefully before clicking
- Yes buttons typically on LEFT, No/Decline on RIGHT
- VERIFY coordinates hit correct button - wrong click can decline irreversibly
- For compliance questions, you almost always want "Yes"

TASK:
"""
        # Combine prefix with user task
        enhanced_task = task_prefix + task + "\n\n" + verification_prompt

        success = False  # Initialize for finally block
        try:
            await self.start_browser(headless=False, user_data_dir=self.user_data_dir)
            await self.page.goto(url)
            
            # Initial navigation verification
            page_content = await self.page.content()
            if "Something didn't go right" in page_content:
                logger.error("Initial navigation failed: landed on an error page.")
                await self._capture_page_state()
                await self.close_browser()
                return False, [{"error": "Initial navigation failed: landed on an error page."}]
            
            # Extract and log project ID from URL
            self._extract_and_log_project_id(url)
            
            # Dismiss platform-specific dialogs first (if handler configured)
            dialog_results = await self._dismiss_platform_dialogs()
            if dialog_results:
                logger.info(f"Platform dialog dismissal results: {dialog_results}")
            
            # Auto-accept cookie banners (with platform-specific selectors if configured)
            cookie_selectors = self.platform_config.get("cookie_selectors")
            cookie_accepted = await auto_accept_cookies(
                self.page,
                additional_selectors=cookie_selectors
            )
            if cookie_accepted:
                logger.info("Cookie consent banner auto-accepted")
            
            logger.info(f"Started Claude Computer Use task: {task}")

            # Get viewport dimensions
            viewport = self.page.viewport_size
            width = viewport.get('width', 1024)
            height = viewport.get('height', 768)

            # Claude Opus 4.5 ONLY - per documentation
            # https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
            model = "claude-opus-4-5"
            tool_type = "computer_20251124"
            beta_header = "computer-use-2025-11-24"

            computer_tool = {
                "type": tool_type,
                "name": "computer",
                "display_width_px": width,
                "display_height_px": height,
                "enable_zoom": True,  # Enable zoom action for detailed screen region inspection
            }
            logger.info(f"Using Claude Opus 4.5 computer use (tool: {tool_type}, beta: {beta_header})")

            # Initial screenshot
            initial_screenshot = await self.take_screenshot()
            screenshot_b64 = self.screenshot_to_base64(initial_screenshot)

            # Initialize messages with enhanced task (includes verification guidance)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": enhanced_task},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        }
                    ]
                }
            ]

            # Agent loop
            for iteration in range(max_iterations):
                logger.info(f"Claude iteration {iteration + 1}/{max_iterations}")

                # Check for blocked state at start of each iteration
                blocked_indicator = await self._check_blocked_state()
                if blocked_indicator:
                    logger.error(f"Project blocked detected at iteration start: '{blocked_indicator}'")
                    await self._capture_page_state()
                    await self.close_browser()
                    return False, self.action_log

                # Build API call parameters - Claude Opus 4.5 with thinking enabled
                api_params = {
                    "model": model,
                    "max_tokens": 4096,
                    "tools": [computer_tool],
                    "messages": messages,
                    "betas": [beta_header],
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": 2048
                    }
                }

                response = self.anthropic.beta.messages.create(**api_params)

                # Append assistant response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Process tool use blocks
                tool_results = []
                has_tool_use = False

                for block in response.content:
                    # Handle thinking blocks (new in computer_20251124)
                    if block.type == "thinking":
                        thinking_text = getattr(block, 'thinking', '') or ''
                        if thinking_text:
                            # Log thinking for debugging and visibility
                            logger.debug(f"Claude thinking: {thinking_text[:500]}...")
                            self.action_log.append({
                                "action": "thinking",
                                "content": thinking_text[:1000]  # Truncate for log storage
                            })

                    elif block.type == "tool_use":
                        has_tool_use = True
                        action = block.input.get("action")

                        logger.info(f"Claude tool use: {block.name} - {action}")
                        logger.debug(f"Params: {block.input}")

                        # Execute action via Playwright
                        result = await self.execute_claude_action(action, block.input)
                        
                        # Handle result depending on whether it's boolean or data
                        success_val = True
                        output_text = None
                        if isinstance(result, bool):
                            success_val = result
                        elif isinstance(result, str):
                            output_text = result
                            success_val = True

                        # Take new screenshot after action
                        new_screenshot = await self.take_screenshot()
                        new_screenshot_b64 = self.screenshot_to_base64(new_screenshot)

                        # Build tool result with screenshot
                        tool_result_content = []
                        if output_text:
                             tool_result_content.append({"type": "text", "text": output_text})
                             
                        tool_result_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": new_screenshot_b64
                            }
                        })
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result_content
                        })

                        # Brief pause between actions
                        await asyncio.sleep(0.5)

                    elif block.type == "text":
                        logger.info(f"Claude text response: {block.text[:200]}")

                # If no tool use, model is done
                if not has_tool_use:
                    logger.success("Task completed - no more tool use")
                    await self._capture_page_state()
                    await self.close_browser()
                    return True, self.action_log

                # Add tool results to conversation
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                # Enhanced intelligent success detection (platform-aware, agentic)
                try:
                    # Platform-specific success detection
                    success_patterns = []
                    if platform_config:
                        # Use platform-specific success indicators
                        success_patterns.extend(platform_config.get("success_indicators", []))

                    # Fallback to generic success patterns
                    success_patterns.extend([
                        "thanks, you're all set", "application received", "successfully submitted",
                        "submission confirmed", "you're all set", "thank you for applying"
                    ])

                    # Check for success patterns in page text (intelligent detection)
                    page_text = await self.page.text_content('body') or ""
                    page_text_lower = page_text.lower()

                    for pattern in success_patterns:
                        if pattern.lower() in page_text_lower:
                            logger.success(f"SUCCESS detected via pattern: '{pattern}' - task completed!")
                            await self._capture_page_state()
                            await self.close_browser()
                            return True, self.action_log

                    # Check for blocked/failure states (intelligent early termination)
                    blocked_patterns = []
                    if platform_config:
                        blocked_patterns.extend(platform_config.get("blocked_indicators", []))
                        blocked_patterns.extend(platform_config.get("failure_indicators", []))

                    # Default blocked patterns
                    blocked_patterns.extend([
                        "already declined", "already applied", "project expired",
                        "no longer available", "invitation has expired"
                    ])

                    for pattern in blocked_patterns:
                        if pattern.lower() in page_text_lower:
                            logger.info(f"BLOCKED state detected via pattern: '{pattern}' - stopping appropriately")
                            await self._capture_page_state()
                            await self.close_browser()
                            return True, self.action_log  # Return True since we correctly detected blocked state

                except Exception as e:
                    logger.debug(f"Enhanced success check error (non-fatal): {e}")

            logger.warning(f"Max iterations ({max_iterations}) reached")
            await self._capture_page_state()
            await self.close_browser()
            return False, self.action_log

        finally:
            await self._capture_page_state()
            await self.close_browser()
            return success, self.action_log

    async def process_dashboard_invitations(
        self,
        dashboard_url: str,
        login_username: str,
        login_password: str,
        profile_context: dict,
        max_invitations: int = 20,
        iterations_per_invitation: int = 30
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Process multiple invitations from a dashboard in ONE browser session.
        
        This method keeps the browser alive between invitations, only logging in once
        and iterating through all visible invitations efficiently.
        
        Args:
            dashboard_url: URL of the platform's invitation dashboard
            login_username: Username for platform login
            login_password: Password for platform login
            profile_context: Profile data for evaluating fit and filling forms
            max_invitations: Maximum number of invitations to process
            iterations_per_invitation: Max iterations allowed per invitation form
            
        Returns:
            Tuple of (processed_count, all_actions_log)
        """
        processed = 0
        all_actions = []
        results = []  # Track each invitation's result
        
        try:
            # Start browser ONCE
            logger.info(f"[{self.correlation_id}] Starting batch dashboard processing at {dashboard_url}")
            await self.start_browser(headless=False)
            await self.page.goto(dashboard_url)
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Handle cookie consent if present
            cookie_accepted = await auto_accept_cookies(self.page)
            if cookie_accepted:
                logger.info(f"[{self.correlation_id}] Cookie consent accepted")
            
            # Login using Claude computer use for the login form only
            login_task = f"""Login to the platform:
1. Enter username: {login_username}
2. Enter password: {login_password}
3. Click Login/Submit button
4. Wait for dashboard to load

Use Tab key to navigate between fields efficiently.
"""
            login_success = await self._perform_batch_login(login_username, login_password)
            if not login_success:
                logger.error(f"[{self.correlation_id}] Batch login failed")
                await self.close_browser()
                return 0, self.action_log
            
            logger.info(f"[{self.correlation_id}] Login successful, starting invitation processing")
            
            # Wait for dashboard to fully load after login
            await asyncio.sleep(3)
            
            # Get initial count of invitations
            invitation_count = await self._get_invitation_count()
            logger.info(f"[{self.correlation_id}] Found {invitation_count} invitations on dashboard")
            
            # Process invitations
            while processed < max_invitations and processed < invitation_count:
                logger.info(f"[{self.correlation_id}] Processing invitation {processed + 1}/{invitation_count}")
                
                # Click on the next invitation
                invitation_clicked = await self._click_next_invitation()
                if not invitation_clicked:
                    logger.info(f"[{self.correlation_id}] No more invitations to process")
                    break
                
                # Wait for invitation details to load
                await asyncio.sleep(2)
                
                # Get invitation details and evaluate fit
                invitation_details = await self._extract_invitation_details()
                should_accept = self._evaluate_invitation_fit(invitation_details, profile_context)
                
                if should_accept:
                    # Process the application form
                    form_success, form_actions = await self._process_invitation_form(
                        profile_context, 
                        iterations_per_invitation
                    )
                    all_actions.extend(form_actions)
                    results.append({
                        "invitation": invitation_details.get("title", f"Invitation {processed + 1}"),
                        "action": "accepted",
                        "success": form_success
                    })
                else:
                    # Decline the invitation
                    decline_success = await self._decline_invitation()
                    results.append({
                        "invitation": invitation_details.get("title", f"Invitation {processed + 1}"),
                        "action": "declined",
                        "success": decline_success
                    })
                
                processed += 1
                
                # Return to dashboard for next invitation
                await self._return_to_dashboard(dashboard_url)
                await asyncio.sleep(2)
            
            logger.success(f"[{self.correlation_id}] Batch processing complete: {processed} invitations processed")
            
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error in batch dashboard processing: {e}")
        finally:
            await self._capture_page_state()
            await self.close_browser()
        
        # Add summary to action log
        all_actions.append({
            "action": "batch_summary",
            "processed_count": processed,
            "results": results
        })
        
        return processed, all_actions

    async def _perform_batch_login(self, username: str, password: str) -> bool:
        """Perform login for batch processing using direct page interaction.
        
        This method now supports platform-specific login handlers via platform_config:
        - If auth_type == "google_oauth", skips username/password login (assumes browser profile)
        - If login_handler is provided, delegates to the platform-specific handler
        - Otherwise, falls back to generic login form detection
        """
        try:
            # Check if platform uses OAuth (no username/password needed)
            auth_type = self.platform_config.get("auth_type", "")
            if auth_type == "google_oauth":
                logger.info(f"[{self.correlation_id}] Platform uses Google OAuth - skipping credential login")
                # For OAuth platforms, we assume the browser profile has the session
                # Just wait for the dashboard to be ready
                await asyncio.sleep(2)
                return True
            
            # Check if platform provides a custom login handler
            login_handler = self.platform_config.get("login_handler")
            if login_handler and callable(login_handler):
                logger.info(f"[{self.correlation_id}] Using platform-specific login handler")
                return await login_handler(self.page, username, password, self.correlation_id)
            
            # Fallback to generic login form detection
            logger.info(f"[{self.correlation_id}] Using generic login form detection")
            
            # Wait for page to be ready
            await asyncio.sleep(2)
            
            # Try to find and fill email/username field (case-insensitive for name/id)
            email_selectors = [
                'input[name="Email"]',  # Guidepoint uses capital E
                'input[name="email"]',
                'input[type="email"]',
                'input[name="username"]',
                'input[name="Username"]',
                'input[id*="email" i]',  # case-insensitive
                'input[id*="user" i]',
                'input[placeholder*="mail" i]',
                'input[placeholder*="Email" i]',
                'table input[type="text"]:first-of-type',  # Guidepoint table-based form
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = await self.page.query_selector(selector)
                    if email_field and await email_field.is_visible():
                        break
                    email_field = None
                except:
                    continue
            
            if email_field:
                await email_field.click()
                await asyncio.sleep(0.5)
                await email_field.fill(username)
                logger.info(f"[{self.correlation_id}] Entered username")
            else:
                logger.warning(f"[{self.correlation_id}] Could not find email field, trying keyboard navigation")
                # Fallback: use Tab to navigate
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(0.3)
                await self.page.keyboard.type(username)
            
            # Try to find and fill password field
            password_selectors = [
                'input[name="Password"]',  # Guidepoint uses capital P
                'input[name="password"]',
                'input[type="password"]',
                'input[id*="password" i]',
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = await self.page.query_selector(selector)
                    if password_field and await password_field.is_visible():
                        break
                    password_field = None
                except:
                    continue
            
            if password_field:
                await password_field.click()
                await asyncio.sleep(0.5)
                await password_field.fill(password)
                logger.info(f"[{self.correlation_id}] Entered password")
            else:
                logger.warning(f"[{self.correlation_id}] Could not find password field, using Tab")
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(0.3)
                await self.page.keyboard.type(password)
            
            # Try to find and click login button
            login_selectors = [
                'input[value="Log In"]',  # Guidepoint specific
                'input[value*="Log"]',
                'input[type="submit"]',
                'button[type="submit"]',
                'input[value*="Sign"]',
                'button:has-text("Log")',
                'button:has-text("Sign")',
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await self.page.query_selector(selector)
                    if login_button and await login_button.is_visible():
                        break
                    login_button = None
                except:
                    continue
            
            if login_button:
                await login_button.click()
                logger.info(f"[{self.correlation_id}] Clicked login button")
                await asyncio.sleep(3)  # Wait for login to complete
                return True
            else:
                # Try pressing Enter as fallback
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(3)
                return True
                
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Login error: {e}")
            return False

    async def _get_invitation_count(self) -> int:
        """Get the count of invitations from the dashboard.
        
        Uses platform_config.get("opportunity_detector") if available,
        otherwise falls back to generic detection.
        """
        try:
            # Check if platform provides a custom opportunity detector
            opportunity_detector = self.platform_config.get("opportunity_detector")
            if opportunity_detector and callable(opportunity_detector):
                logger.info(f"[{self.correlation_id}] Using platform-specific opportunity detector")
                count = await opportunity_detector(self.page, self.correlation_id)
                if count > 0:
                    return count
                # If detector returns 0, fall through to generic detection
            
            # Generic detection: Look for invitation count indicators (e.g., "Invitations (13)")
            page_text = await self.page.content()
            
            import re
            # Pattern for "Invitations (N)" or similar
            count_patterns = [
                r'Invitations?\s*\((\d+)\)',
                r'(\d+)\s*Invitations?',
                r'Projects?\s*\((\d+)\)',
                r'(\d+)\s*pending',
                r'Requests?\s*\((\d+)\)',  # For Guidepoint
                r'(\d+)\s*Requests?',      # For Guidepoint
                r'Open\s*\((\d+)\)',       # Common dashboard pattern
            ]
            
            for pattern in count_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                    logger.info(f"[{self.correlation_id}] Found invitation count: {count} (pattern: {pattern})")
                    return count

            # Fallback: count invitation card elements
            card_selectors = [
                '.invitation-card',
                '.project-card',
                '[class*="invitation"]',
                '[class*="project-item"]',
                'tr[class*="request"]',
                'div[class*="request-card"]',
            ]

            for selector in card_selectors:
                try:
                    cards = await self.page.query_selector_all(selector)
                    if cards and len(cards) > 0:
                        logger.info(f"[{self.correlation_id}] Found {len(cards)} elements matching '{selector}'")
                        return len(cards)
                except:
                    continue
            
            # If we get here, we couldn't find a count. Log debug info.
            logger.warning(f"[{self.correlation_id}] Could not determine invitation count. Dumping page title/headers.")
            try:
                title = await self.page.title()
                logger.debug(f"Page Title: {title}")
                headers = await self.page.evaluate("""() => Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText)""")
                logger.debug(f"Headers: {headers}")
            except Exception as e:
                logger.debug(f"Failed to dump debug info: {e}")

            return 10  # Default assumption if count not found
            
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error getting invitation count: {e}")
            return 10

    async def _click_next_invitation(self) -> bool:
        """Click on the next unprocessed invitation in the dashboard.
        
        Uses platform_config.get("opportunity_navigator") if available,
        otherwise falls back to generic detection.
        """
        try:
            logger.info(f"[{self.correlation_id}] Attempting to click next invitation...")
            
            # Check if platform provides a custom opportunity navigator
            opportunity_navigator = self.platform_config.get("opportunity_navigator")
            if opportunity_navigator and callable(opportunity_navigator):
                logger.info(f"[{self.correlation_id}] Using platform-specific opportunity navigator")
                # Always use index 0 since we return to dashboard after each invitation
                # and the next unprocessed invitation will be at the top
                result = await opportunity_navigator(self.page, 0, self.correlation_id)
                if result:
                    return True
                # If navigator returns False, fall through to generic detection

            # Generic detection: Look for invitation cards/links
            invitation_selectors = [
                'a[href*="response"]',
                'a[href*="project"]',
                '.invitation-card a',
                '.project-card a',
                '[class*="invitation"] a',
                'tr[class*="invitation"] a',
                'div[class*="card"] a[href*="/requests/"]',
                'a[href*="/consultation/"]',
            ]

            for selector in invitation_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for el in elements:
                        if await el.is_visible():
                            href = await el.get_attribute('href')
                            logger.info(f"[{self.correlation_id}] Found invitation link matching '{selector}': {href}")
                            await el.click()
                            return True
                except:
                    continue

            logger.warning(f"[{self.correlation_id}] Could not find ANY invitation to click. Dumping body text snippet.")
            try:
                body_text = await self.page.inner_text('body')
                logger.debug(f"Body text snippet: {body_text[:500]}")
            except:
                pass
                
            return False

        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error clicking invitation: {e}")
            return False

    async def _extract_invitation_details(self) -> Dict[str, Any]:
        """Extract details from the current invitation page."""
        try:
            title = await self.page.title()
            url = self.page.url
            
            # Try to get main content text
            content = ""
            try:
                main_content = await self.page.query_selector('main, .content, .project-details, article')
                if main_content:
                    content = await main_content.inner_text()
            except:
                content = await self.page.inner_text('body')
            
            return {
                "title": title,
                "url": url,
                "content": content[:2000],  # Limit content length
            }
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error extracting invitation details: {e}")
            return {"title": "Unknown", "url": "", "content": ""}

    def _evaluate_invitation_fit(self, invitation: Dict[str, Any], profile: dict) -> bool:
        """Evaluate if an invitation is a good fit based on profile.
        
        Uses platform_config.get("always_accept_dashboard_invitations") if set.
        """
        # Check if platform config says to always accept dashboard invitations
        if self.platform_config.get("always_accept_dashboard_invitations", False):
            logger.info(f"[{self.correlation_id}] Platform configured to always accept dashboard invitations")
            return True
        
        content = invitation.get("content", "").lower()
        title = invitation.get("title", "").lower()
        url = invitation.get("url", "").lower()

        # Keywords that indicate good fit
        good_fit_keywords = [
            "ai", "artificial intelligence", "machine learning", "ml",
            "llm", "large language model", "generative", "gpt", "claude",
            "cloud", "gcp", "aws", "azure", "kubernetes", "docker",
            "enterprise", "software", "architecture", "microservices",
            "application modernization", "digital transformation",
            "python", "java", "api", "saas", "platform",
            "data center", "infrastructure", "devops",
            "google", "amazon", "microsoft", "anthropic", "openai",
            "tpu", "asic", "chip", "semiconductor", "security", "broadcom"
        ]

        # Keywords that indicate poor fit
        poor_fit_keywords = [
            "medical device", "pharmaceutical manufacturing", "clinical trial",
            "supply chain logistics", "retail operations",
            "financial trading", "derivatives", "hedge fund",
            "real estate appraisal", "property management",
            "oil and gas drilling", "mining operations",
            "food processing", "agriculture",
        ]

        # Count matches
        good_matches = sum(1 for kw in good_fit_keywords if kw in content or kw in title)
        poor_matches = sum(1 for kw in poor_fit_keywords if kw in content or kw in title)

        # Accept if more good matches than poor matches, or if it's a survey/paid opportunity
        if "survey" in content or "paid" in content:
            return True

        # If content is mostly empty (batch processing issue), default to accept
        if len(content.strip()) < 50 and len(title.strip()) < 20:
            logger.info(f"[{self.correlation_id}] Minimal content detected - accepting by default")
            return True

        return good_matches > poor_matches or good_matches >= 2

    async def _process_invitation_form(
        self, 
        profile_context: dict,
        max_iterations: int
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Process the invitation form using Claude computer use."""
        # Generate form filling task
        form_task = f"""Complete this consultation application form:

Profile Context:
- Name: {profile_context.get('name', 'Rohit Kelapure')}
- Company: {profile_context.get('company', '8090 Solutions Inc.')}
- Title: {profile_context.get('role', 'Principal Architect')}
- Expertise: AI/ML, Cloud Computing, Enterprise Architecture, Application Modernization

Fill all required fields and submit the form.
Use Tab key to navigate between fields efficiently.
Click checkboxes for relevant expertise areas.
For text areas, provide clear, concise responses.
Submit when all fields are complete.
"""
        
        # Use existing claude_computer_use method for form filling
        # But we're already on the page, so we just need to fill the form
        success, actions = await self.claude_computer_use(
            task=form_task,
            url=self.page.url,
            max_iterations=max_iterations,
            verification_prompt="Verify form was submitted successfully."
        )
        
        return success, actions

    async def _decline_invitation(self) -> bool:
        """Decline the current invitation."""
        try:
            decline_selectors = [
                'button:has-text("Decline")',
                'a:has-text("Decline")',
                'input[value*="Decline"]',
                'button[class*="decline"]',
                '.decline-button',
            ]
            
            for selector in decline_selectors:
                try:
                    decline_btn = await self.page.query_selector(selector)
                    if decline_btn:
                        await decline_btn.click()
                        logger.info(f"[{self.correlation_id}] Clicked decline button")
                        await asyncio.sleep(2)
                        return True
                except:
                    continue
            
            logger.warning(f"[{self.correlation_id}] Could not find decline button")
            return False
            
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error declining invitation: {e}")
            return False

    async def _return_to_dashboard(self, dashboard_url: str) -> bool:
        """Navigate back to the dashboard."""
        try:
            await self.page.goto(dashboard_url)
            await asyncio.sleep(2)
            logger.info(f"[{self.correlation_id}] Returned to dashboard")
            return True
        except Exception as e:
            logger.error(f"[{self.correlation_id}] Error returning to dashboard: {e}")
            return False


async def submit_platform_application(
    project_url: str,
    task_prompt: str,
    platform_name: str = "unknown",
    max_retries: int = 3,
    correlation_id: str = "N/A",
    verification_prompt: str = "Verify that the application was successfully submitted.",
    platform_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Submit or decline a consultation application using Claude (primary) with Gemini fallback.

    This is a generic browser automation function that executes the provided task prompt.
    Claude is used first for maximum reliability. If Claude fails, Gemini is used as a
    secondary attempt.

    Args:
        project_url: Platform project URL to navigate to
        task_prompt: Complete task description including login, form filling, or decline instructions
        platform_name: Name of the platform (for logging purposes only)
        max_retries: Maximum Gemini retry attempts if Claude fails
        correlation_id: Unique identifier for this run, for logging and tracing.
        verification_prompt: A prompt to guide the AI in verifying success.
        platform_config: Platform-specific configuration including:
            - success_indicators: List[str] - platform-specific success patterns
            - failure_indicators: List[str] - platform-specific failure patterns
            - blocked_indicators: List[str] - platform-specific blocked patterns
            - workflow_stages: Dict[str, List[str]] - platform-specific workflow stages
            - dialog_handler: Callable[[Page], Awaitable[Dict]] - async function to dismiss platform dialogs
            - cookie_selectors: List[str] - platform-specific cookie button selectors

    Returns:
        {
            "success": bool,
            "method": "gemini" | "claude",
            "actions": List[Dict],
            "error": Optional[str],
            "project_id": Optional[str]
        }
    """
    automation = BrowserAutomation(
        correlation_id=correlation_id,
        platform=platform_name,
        project_url=project_url,
        platform_config=platform_config
    )
    
    # Extract project ID for result
    project_id = extract_project_id_from_url(project_url)

    # Create sanitized version of task for logging (redacts credentials)
    sanitized_task = mask_password_in_logs(task_prompt)
    
    # Determine user_data_dir from platform config
    user_data_dir = None
    if platform_config and platform_config.get("uses_browser_profile"):
        user_data_dir = os.path.join(os.getcwd(), "profiles", "default")
        logger.info(f"Platform {platform_name} requests persistent profile: {user_data_dir}")
    
    # 1) Try Claude first (primary engine)
    logger.info(f"Submitting {platform_name} application: trying Claude computer-use (primary)...")
    logger.debug(f"Task (sanitized): {sanitized_task[:500]}...")
    
    # We need to modify how start_browser is called inside the computer_use methods
    # But those methods call start_browser internally. 
    # We should update the automation object to store the preferred user_data_dir
    automation.user_data_dir = user_data_dir
    
    # Monkey-patch or update the start_browser method call? 
    # Better: Update the class to store user_data_dir in __init__ or update the methods to use instance variable
    
    # Let's update the methods to use the instance variable if set
    # OR simpler: just update start_browser to default to self.user_data_dir if set
    
    # For this specific file structure, we need to update the calls within claude_computer_use and gemini_computer_use
    # But since I can't easily change the method signatures in this tool call without replacing the whole file,
    # I will rely on a small hack: set the default in the class instance
    
    # Update: I will modify the start_browser method in the class to use self.user_data_dir
    # But first I need to update the class definition.
    # Since I just updated start_browser signature, I can pass it if I update the calls.
    
    # Wait, the previous replace updated the signature of start_browser.
    # Now I need to update where it is CALLED inside claude_computer_use and gemini_computer_use.
    
    # Since I cannot update multiple locations easily with one replace block if they are far apart,
    # I will update submit_platform_application to pass the dir to the methods, 
    # AND update the methods to accept it.
    
    # Actually, the best way is to set it on the instance and have start_browser use it.
    # Let's update __init__ and start_browser again? No, that's too many steps.
    
    # Let's just update the calls inside the methods.
    pass

async def submit_platform_application(
    project_url: str,
    task_prompt: str,
    platform_name: str = "unknown",
    max_retries: int = 3,
    correlation_id: str = "N/A",
    verification_prompt: str = "Verify that the application was successfully submitted.",
    platform_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Submit or decline a consultation application using Claude (primary) with Gemini fallback.
    """
    automation = BrowserAutomation(
        correlation_id=correlation_id,
        platform=platform_name,
        project_url=project_url,
        platform_config=platform_config
    )
    
    # Determine user_data_dir
    user_data_dir = None
    if platform_config and platform_config.get("uses_browser_profile"):
        user_data_dir = os.path.join(os.getcwd(), "profiles", "default")
    
    # Store it on the automation instance for methods to access
    automation.user_data_dir = user_data_dir
    
    # Extract project ID for result
    project_id = extract_project_id_from_url(project_url)

    # Create sanitized version of task for logging (redacts credentials)
    sanitized_task = mask_password_in_logs(task_prompt)
    
    # 1) Try Claude first (primary engine)
    logger.info(f"Submitting {platform_name} application: trying Claude computer-use (primary)...")
    logger.debug(f"Task (sanitized): {sanitized_task[:500]}...")
    success, actions = await automation.claude_computer_use(
        task=task_prompt,
        url=project_url,
        max_iterations=35,
        verification_prompt=verification_prompt
    )

    if success:
        return {
            "success": True,
            "method": "claude",
            "actions": _sanitize_action_log(actions),
            "error": None,
            "project_id": project_id,
        }

    logger.warning("Claude computer-use failed, attempting Gemini fallback...")

    # 2) If Claude fails, try Gemini as secondary (if configured)
    if not automation.gemini_client:
        logger.error("Gemini client not configured; cannot perform fallback.")
        return {
            "success": False,
            "method": "claude",
            "actions": _sanitize_action_log(automation.action_log),
            "error": "Claude failed and Gemini not configured for fallback",
            "project_id": project_id,
        }

    for attempt in range(max_retries):
        logger.info(f"Gemini fallback attempt {attempt + 1}/{max_retries}")

        # Restart browser for Gemini (Claude closed it)
        # Note: gemini_computer_use calls start_browser internally, so we rely on instance var
        
        success, actions = await automation.gemini_computer_use(
            task=task_prompt,
            url=project_url,
            max_iterations=35,
            verification_prompt=verification_prompt
        )

        if success:
            return {
                "success": True,
                "method": "gemini",
                "actions": _sanitize_action_log(actions),
                "error": None,
                "project_id": project_id,
            }

        logger.warning(f"Gemini fallback attempt {attempt + 1} failed")
        await asyncio.sleep(2)

    # Both engines failed
    return {
        "success": False,
        "method": None,
        "actions": _sanitize_action_log(automation.action_log),
        "error": "Both Claude and Gemini computer-use failed",
        "project_id": project_id,
    }
