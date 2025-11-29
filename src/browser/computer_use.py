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

    async def start_browser(self, headless: bool = None):
        """
        Start Playwright browser.

        Args:
            headless: Override headless mode. If None, reads from HEADLESS env var (default: False)
        """
        # Environment detection
        if headless is None:
            headless = os.getenv('HEADLESS', 'false').lower() in ('true', '1', 'yes')

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()
        self.action_log = []
        self.last_page_state = {}

        mode = "headless" if headless else "headed"
        logger.info(f"[{self.correlation_id}] Browser started ({mode} mode)")

    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            logger.info(f"[{self.correlation_id}] Browser closed")
        self.page = None
        self.browser = None

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

                # Check if we've clicked this location recently (within 20px tolerance)
                tolerance = 20
                recent_clicks_at_location = sum(
                    1 for px, py in self._click_history[-5:]  # Check last 5 clicks
                    if abs(px - x) < tolerance and abs(py - y) < tolerance
                )
                
                # Track this click
                self._click_history.append((x, y))
                if len(self._click_history) > 10:
                    self._click_history = self._click_history[-10:]
                
                # Use JS fallback if we've clicked same spot multiple times
                if recent_clicks_at_location >= self._click_fallback_threshold:
                    logger.warning(f"Detected {recent_clicks_at_location} repeated clicks at ({x}, {y}), using JS fallback")
                    if await self._js_click_fallback(x, y):
                        self._log_action({"action": "click_at", "x": x, "y": y, "method": "js_fallback"})
                        return True
                    logger.warning(f"[{self.correlation_id}] JS fallback failed, trying normal click anyway")
                
                await self.page.mouse.click(x, y)
                logger.info(f"[{self.correlation_id}] Clicked at: ({x}, {y}) [normalized: ({x_norm}, {y_norm})]")
                self._log_action({"action": "click_at", "x": x, "y": y})
                return True

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
        verification_prompt: str = "Verify that the application was successfully submitted."
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Use Gemini 2.5 Computer Use API to complete a browser task.

        Uses model: gemini-2.5-computer-use-preview-10-2025
        Per documentation: https://ai.google.dev/gemini-api/docs/computer-use

        Args:
            task: Description of what to accomplish
            url: Starting URL
            max_iterations: Maximum number of AI iterations

        Returns:
            (success, action_log)
        """
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
            await self.start_browser(headless=False)
            await self.page.goto(url)
            
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

                # Check if success message is visible (programmatic success detection)
                try:
                    success_visible = await self.page.evaluate("""
                        () => {
                            const successMsg = document.getElementById('success-message');
                            if (!successMsg) return false;
                            const style = window.getComputedStyle(successMsg);
                            return style.display !== 'none' && style.visibility !== 'hidden';
                        }
                    """)
                    if success_visible:
                        logger.success("Success message detected - form submitted successfully!")
                        await self._capture_page_state()
                        await self.close_browser()
                        return True, self.action_log
                except Exception as e:
                    logger.debug(f"Success check error (non-fatal): {e}")

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

                for key in keys_to_press:
                    mapped_key = key_mapping.get(key, key)
                    await self.page.keyboard.press(mapped_key)
                    logger.info(f"[{self.correlation_id}] Claude: Pressed key: {mapped_key} (original: {key})")
                    # Small delay between key presses if multiple are sent
                    if len(keys_to_press) > 1:
                        await asyncio.sleep(0.1)

                self._log_action({"action": "key", "text": keys_string})
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
        max_iterations: int = 35,
        verification_prompt: str = "Verify that the application was successfully submitted."
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

        # Task prompt prefix with verification and UI guidance
        task_prefix = """IMPORTANT INSTRUCTIONS FOR FORM FILLING:

1. After each action, verify the outcome in the next screenshot.
   - Only proceed to the next step after confirming success

2. **CRITICAL - For dropdown/select elements:**
   - DO NOT try clicking to open dropdowns - this often doesn't work
   - INSTEAD: Click on the dropdown field, then immediately TYPE the desired option text
   - The system will automatically select the matching option
   - Example: To select "VP / Senior Director", click the dropdown then type "VP"

3. For checkboxes and radio buttons:
   - Click directly on the checkbox/radio element itself
   - Verify the checked state in the next screenshot

4. For text inputs:
   - Click the field, then type the text

5. Keyboard shortcuts:
   - Tab: Move to next field
   - Space: Toggle checkboxes
   - Enter: Submit form

6. Be efficient - complete each field in 1-2 actions, not multiple attempts.

7. **CRITICAL - Yes/No Questions:**
   - Before clicking Yes or No, READ THE BUTTON TEXT carefully
   - Yes buttons are typically on the LEFT side, No/Decline buttons on the RIGHT
   - VERIFY the button coordinates hit the CORRECT button - clicking wrong can decline the project irreversibly
   - For compliance questions asking if you can participate, you almost always want "Yes"
   - If a button click doesn't work after 2 attempts, try clicking with slight offset or use keyboard navigation

TASK:
"""
        # Combine prefix with user task
        enhanced_task = task_prefix + task + "\n\n" + verification_prompt

        try:
            await self.start_browser(headless=False)
            await self.page.goto(url)
            
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
                        success = await self.execute_claude_action(action, block.input)

                        # Take new screenshot after action
                        new_screenshot = await self.take_screenshot()
                        new_screenshot_b64 = self.screenshot_to_base64(new_screenshot)

                        # Build tool result with screenshot
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": new_screenshot_b64
                                    }
                                }
                            ]
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

                # Check if success message is visible (programmatic success detection)
                try:
                    success_visible = await self.page.evaluate("""
                        () => {
                            const successMsg = document.getElementById('success-message');
                            if (!successMsg) return false;
                            const style = window.getComputedStyle(successMsg);
                            return style.display !== 'none' && style.visibility !== 'hidden';
                        }
                    """)
                    if success_visible:
                        logger.success("Success message detected - form submitted successfully!")
                        await self._capture_page_state()
                        await self.close_browser()
                        return True, self.action_log
                except Exception as e:
                    logger.debug(f"Success check error (non-fatal): {e}")

            logger.warning(f"Max iterations ({max_iterations}) reached")
            await self._capture_page_state()
            await self.close_browser()
            return False, self.action_log

        finally:
            await self._capture_page_state()
            await self.close_browser()
            return success, self.action_log


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
        await automation.start_browser(headless=False)

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
