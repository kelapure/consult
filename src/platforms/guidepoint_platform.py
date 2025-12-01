"""Guidepoint platform implementation.

This module contains ALL Guidepoint-specific code:
- Cookie/language dialog handling
- Success/failure/blocked indicators
- Form field templates with answering strategies
- Workflow stages for multi-step applications
- Task prompt generation for browser automation

The core browser automation (computer_use.py) and cookie detection
(cookie_detection.py) remain platform-agnostic.
"""

import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from playwright.async_api import Page

from .base import BasePlatform
from src.browser.cookie_detection import dismiss_dialog_by_selectors
from src.browser.computer_use import smart_element_click


# =============================================================================
# GUIDEPOINT-SPECIFIC SUCCESS/FAILURE/BLOCKED INDICATORS
# =============================================================================

GUIDEPOINT_SUCCESS_INDICATORS = [
    # Guidepoint-specific success messages
    "thank you for your response",
    "response submitted",
    "successfully submitted",
    "we appreciate your time",
    "your response has been recorded",
    "submission complete",
    "thank you for completing",
]

GUIDEPOINT_FAILURE_INDICATORS = [
    # Guidepoint-specific failure messages
    "request has expired",
    "consultation is no longer available",
    "unable to process your request",
    "an error occurred",
    "something went wrong",
    "please try again later",
]

GUIDEPOINT_BLOCKED_INDICATORS = [
    # Guidepoint-specific blocked states
    "already responded",
    "already submitted",
    "request expired",
    "link has expired",
    "no longer accepting responses",
    "consultation closed",
]


# =============================================================================
# GUIDEPOINT-SPECIFIC WORKFLOW STAGES
# =============================================================================

GUIDEPOINT_WORKFLOW_STAGES = {
    "rate_limit": ["rate limit", "hourly rate", "rate for this project", "accept or decline"],
    "ai_agreement": ["artificial intelligence", "ai tools", "third-party sources", "agree to participate"],
    "client_screening": ["current employer", "current title", "profile up to date", "senior person"],
    "expert_screening": ["screening questions", "industry experts", "outline your experience", "suitability"],
    "compliance": ["terms and conditions", "privacy policy", "advisor compliance tutorial", "checking this box"],
    "final_submit": ["submit", "send response", "confirm submission"],
    "completion": ["thank you", "response submitted", "successfully submitted"],
}


# =============================================================================
# GUIDEPOINT-SPECIFIC DIALOG SELECTORS
# =============================================================================

# Language selector dialog (Guidepoint supports multiple languages)
GUIDEPOINT_LANGUAGE_DIALOG = {
    "dialog_selectors": [
        'select[name="language"]',
        '.language-selector',
        '[class*="language"]',
    ],
    "dismiss_selectors": [
        'option[value="en"]',
        'option:has-text("English")',
    ],
    "description": "Guidepoint language selector"
}

# Cookie consent banner
GUIDEPOINT_COOKIE_BANNER = {
    "dialog_selectors": [
        '#cookie-banner',
        '.cookie-consent',
        '[class*="cookie"]',
        '[id*="cookie"]',
    ],
    "dismiss_selectors": [
        'button:has-text("Accept")',
        'button:has-text("Allow")',
        'a:has-text("Cookie Preferences")',
        'button:has-text("OK")',
    ],
    "description": "Guidepoint cookie banner"
}

# Additional Guidepoint cookie button selectors (for core cookie detection)
GUIDEPOINT_COOKIE_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Allow All")',
    'button:has-text("OK")',
    'a:has-text("Cookie Preferences")',
]


# =============================================================================
# GUIDEPOINT-SPECIFIC FORM FIELD TEMPLATES
# =============================================================================

# Standard responses for client screening questions
GUIDEPOINT_CLIENT_SCREENING_STRATEGY = {
    "senior_role": {
        # Q1: Are you currently the most senior person in your organization?
        "answer": "No",
        "explanation": "I am a Principal Consultant focused on technical delivery and client advisory.",
    },
    "employer": {
        # Q2: Please state your current employer(s)
        "answer": "Independent Consultant / Self-Employed",
    },
    "title": {
        # Q3: Please state your current title(s)
        "answer": "Principal Consultant - Cloud & AI Solutions",
    },
    "profile_updated": {
        # Q4: Is your Guidepoint profile up to date?
        "answer": "Yes",
    },
}


# =============================================================================
# GUIDEPOINT DIALOG HANDLER
# =============================================================================

async def dismiss_guidepoint_cookie_banner(page: Page) -> bool:
    """
    Dismiss Guidepoint's cookie consent banner.

    Args:
        page: Playwright page object

    Returns:
        True if banner was found and dismissed, False otherwise
    """
    return await dismiss_dialog_by_selectors(
        page,
        dialog_selectors=GUIDEPOINT_COOKIE_BANNER["dialog_selectors"],
        dismiss_selectors=GUIDEPOINT_COOKIE_BANNER["dismiss_selectors"],
        description=GUIDEPOINT_COOKIE_BANNER["description"]
    )


async def set_guidepoint_language_english(page: Page) -> bool:
    """
    Ensure Guidepoint is set to English language.

    Args:
        page: Playwright page object

    Returns:
        True if language was set or already English, False otherwise
    """
    try:
        # Look for language selector
        language_selector = await page.query_selector('select')
        if language_selector:
            # Check if it's a language selector
            options = await page.query_selector_all('select option')
            for option in options:
                text = await option.text_content()
                if text and 'english' in text.lower():
                    await language_selector.select_option(label=text.strip())
                    logger.info("Set Guidepoint language to English")
                    return True
        return False
    except Exception as e:
        logger.debug(f"Could not set language: {e}")
        return False


async def dismiss_all_guidepoint_dialogs(page: Page, max_iterations: int = 5) -> Dict[str, Any]:
    """
    Dismiss all known Guidepoint-specific dialogs in sequence.

    This is the main entry point for Guidepoint dialog handling. It handles:
    - Cookie consent
    - Language selection (set to English)
    - Any other persistent dialogs

    Args:
        page: Playwright page object
        max_iterations: Maximum iterations to handle persistent dialogs

    Returns:
        Dict with results for each dialog type:
        {
            "cookie_banner": bool,
            "language_set": bool,
            "iterations": int
        }
    """
    results = {
        "cookie_banner": False,
        "language_set": False,
        "iterations": 0
    }

    for iteration in range(max_iterations):
        results["iterations"] = iteration + 1
        dismissed_any = False

        # 1. Try cookie banner first
        if not results["cookie_banner"]:
            if await dismiss_guidepoint_cookie_banner(page):
                results["cookie_banner"] = True
                dismissed_any = True
                await asyncio.sleep(0.3)

        # 2. Set language to English if selector exists
        if not results["language_set"]:
            if await set_guidepoint_language_english(page):
                results["language_set"] = True
                dismissed_any = True
                await asyncio.sleep(0.3)

        # If nothing was dismissed, we're done
        if not dismissed_any:
            break

        logger.debug(f"Guidepoint dialog dismissal iteration {iteration + 1}: {results}")

    return results


# =============================================================================
# GUIDEPOINT DASHBOARD HANDLERS
# =============================================================================

async def enhanced_guidepoint_dashboard_login(
    page: Page,
    username: str,
    password: str,
    correlation_id: str = "N/A"
) -> bool:
    """
    Enhanced login handler for Guidepoint dashboard.
    
    Uses smart_element_click for robust element detection and handles
    Guidepoint-specific login form patterns.
    
    Args:
        page: Playwright page object
        username: Guidepoint username (email)
        password: Guidepoint password
        correlation_id: Optional ID for logging context
        
    Returns:
        True if login succeeded, False otherwise
    """
    try:
        # Wait for page to be ready
        await asyncio.sleep(2)
        
        # Guidepoint uses specific field names with capital letters
        email_strategies = [
            {"type": "css", "selector": 'input[name="Email"]', "description": "Email field by name"},
            {"type": "css", "selector": 'input[type="email"]', "description": "Email field by type"},
            {"type": "css", "selector": 'input[id*="email" i]', "description": "Email field by id"},
            {"type": "css", "selector": 'table input[type="text"]:first-of-type', "description": "Table-based email field"},
        ]
        
        # Find and fill email field
        email_filled = False
        for strategy in email_strategies:
            try:
                element = await page.query_selector(strategy["selector"])
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(0.3)
                    await element.fill(username)
                    logger.info(f"[{correlation_id}] Guidepoint: Entered username via {strategy['description']}")
                    email_filled = True
                    break
            except Exception as e:
                logger.debug(f"[{correlation_id}] Email strategy failed: {strategy['description']} - {e}")
                continue
        
        if not email_filled:
            logger.warning(f"[{correlation_id}] Could not find email field")
            return False
        
        # Find and fill password field
        password_strategies = [
            {"type": "css", "selector": 'input[name="Password"]', "description": "Password field by name"},
            {"type": "css", "selector": 'input[type="password"]', "description": "Password field by type"},
            {"type": "css", "selector": 'input[id*="password" i]', "description": "Password field by id"},
        ]
        
        password_filled = False
        for strategy in password_strategies:
            try:
                element = await page.query_selector(strategy["selector"])
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(0.3)
                    await element.fill(password)
                    logger.info(f"[{correlation_id}] Guidepoint: Entered password via {strategy['description']}")
                    password_filled = True
                    break
            except Exception as e:
                logger.debug(f"[{correlation_id}] Password strategy failed: {strategy['description']} - {e}")
                continue
        
        if not password_filled:
            logger.warning(f"[{correlation_id}] Could not find password field")
            return False
        
        # Click login button using smart_element_click
        login_strategies = [
            {"type": "css", "selector": 'input[value="Log In"]', "description": "Guidepoint Log In button"},
            {"type": "css", "selector": 'input[type="submit"]', "description": "Submit input"},
            {"type": "text", "selector": 'button:has-text("Log")', "description": "Login button by text"},
            {"type": "text", "selector": 'button:has-text("Sign")', "description": "Sign in button"},
        ]
        
        login_clicked = await smart_element_click(page, login_strategies, correlation_id)
        
        if login_clicked:
            await asyncio.sleep(3)  # Wait for login to complete
            logger.info(f"[{correlation_id}] Guidepoint login completed")
            return True
        else:
            # Fallback: press Enter
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)
            logger.info(f"[{correlation_id}] Guidepoint login attempted via Enter key")
            return True
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Guidepoint login error: {e}")
        return False


async def detect_guidepoint_opportunities(
    page: Page,
    correlation_id: str = "N/A"
) -> int:
    """
    Detect the number of Guidepoint opportunities on the dashboard.
    
    Args:
        page: Playwright page object
        correlation_id: Optional ID for logging context
        
    Returns:
        Number of opportunities detected
    """
    try:
        import re
        page_text = await page.content()
        
        # Guidepoint-specific patterns
        count_patterns = [
            r'Requests?\s*\((\d+)\)',
            r'(\d+)\s*Requests?',
            r'Open\s*\((\d+)\)',
            r'Pending\s*\((\d+)\)',
        ]
        
        for pattern in count_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                logger.info(f"[{correlation_id}] Guidepoint: Found {count} opportunities (pattern: {pattern})")
                return count
        
        # Fallback: count table rows with request data
        try:
            rows = await page.query_selector_all('tr[class*="request"], div[class*="request-card"]')
            if rows:
                logger.info(f"[{correlation_id}] Guidepoint: Found {len(rows)} request elements")
                return len(rows)
        except Exception:
            pass
        
        logger.warning(f"[{correlation_id}] Guidepoint: Could not determine opportunity count")
        return 0
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Guidepoint opportunity detection error: {e}")
        return 0


async def navigate_to_opportunity_application(
    page: Page,
    index: int = 0,
    correlation_id: str = "N/A"
) -> bool:
    """
    Navigate to a specific Guidepoint opportunity for application.
    
    Args:
        page: Playwright page object
        index: Index of the opportunity to navigate to (0-based)
        correlation_id: Optional ID for logging context
        
    Returns:
        True if navigation succeeded, False otherwise
    """
    try:
        # Guidepoint opportunity link strategies
        opportunity_strategies = [
            {"type": "css", "selector": 'a[href*="response"]', "description": "Response link"},
            {"type": "css", "selector": 'a[href*="/requests/"]', "description": "Request link"},
            {"type": "css", "selector": 'a[href*="/consultation/"]', "description": "Consultation link"},
            {"type": "text", "selector": 'a:has-text("Respond")', "description": "Respond link"},
            {"type": "text", "selector": 'a:has-text("View Request")', "description": "View Request link"},
        ]
        
        # Try to find all matching elements and click the one at index
        for strategy in opportunity_strategies:
            try:
                selector = strategy["selector"]
                if strategy["type"] == "css":
                    elements = await page.query_selector_all(selector)
                else:
                    locator = page.locator(selector)
                    count = await locator.count()
                    elements = [await locator.nth(i).element_handle() for i in range(count)]
                
                # Filter for visible elements
                visible_elements = []
                for el in elements:
                    if el and await el.is_visible():
                        visible_elements.append(el)
                
                if visible_elements and index < len(visible_elements):
                    await visible_elements[index].click()
                    logger.info(f"[{correlation_id}] Guidepoint: Navigated to opportunity {index + 1} via {strategy['description']}")
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                logger.debug(f"[{correlation_id}] Guidepoint navigation strategy failed: {strategy['description']} - {e}")
                continue
        
        # Fallback: use smart_element_click for first opportunity
        if index == 0:
            clicked = await smart_element_click(page, opportunity_strategies, correlation_id)
            if clicked:
                await asyncio.sleep(2)
                return True
        
        logger.warning(f"[{correlation_id}] Guidepoint: Could not navigate to opportunity {index + 1}")
        return False
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Guidepoint navigation error: {e}")
        return False


def get_guidepoint_platform_config() -> Dict[str, Any]:
    """
    Get the platform configuration for Guidepoint.
    
    This configuration is passed to BrowserAutomation to enable
    Guidepoint-specific behavior without hardcoding it in the core module.
    
    Returns:
        Platform configuration dict for BrowserAutomation
    """
    return {
        "success_indicators": GUIDEPOINT_SUCCESS_INDICATORS,
        "failure_indicators": GUIDEPOINT_FAILURE_INDICATORS,
        "blocked_indicators": GUIDEPOINT_BLOCKED_INDICATORS,
        "workflow_stages": GUIDEPOINT_WORKFLOW_STAGES,
        "dialog_handler": dismiss_all_guidepoint_dialogs,
        "cookie_selectors": GUIDEPOINT_COOKIE_SELECTORS,
        # Platform-specific handlers for decoupled browser automation
        "login_handler": enhanced_guidepoint_dashboard_login,
        "opportunity_detector": detect_guidepoint_opportunities,
        "opportunity_navigator": navigate_to_opportunity_application,
    }


# =============================================================================
# GUIDEPOINT TASK PROMPT GENERATION
# =============================================================================

def build_guidepoint_task_prompt(
    form_data: Dict[str, Any],
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    decline: bool = False
) -> str:
    """
    Build a Guidepoint-specific task prompt for browser automation.
    
    This generates detailed instructions for the AI to complete
    Guidepoint's multi-step consultation response form.
    
    Args:
        form_data: Form field data to fill
        login_username: Guidepoint username if login needed
        login_password: Guidepoint password if login needed
        decline: Whether to decline instead of accept
        
    Returns:
        Complete task prompt string
    """
    if decline:
        prompt = """DECLINE the Guidepoint consultation opportunity.

"""
        if login_username and login_password:
            prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
        prompt += """Navigate to the consultation form and:

1. **Rate Limit Section**: Click "Decline" for the rate limit question.
2. **AI Agreement Section**: Select "I do not agree" (since you're declining).
3. **Submit**: Click Submit or Send Response to confirm the decline.

Verify you see a confirmation message before finishing.
"""
        return prompt
    
    # Accept workflow
    prompt = """Complete the Guidepoint consultation response form.

**CRITICAL - GUIDEPOINT MULTI-STEP WORKFLOW:**
Guidepoint forms have multiple sections. You MUST complete ALL sections:

1. **Rate Limit Acceptance** (if present):
   - Click "Accept" to accept the project's rate limit
   - This confirms you agree to the hourly rate for this consultation

2. **AI Tools Agreement** (IMPORTANT - Required):
   - Select "I agree" to the terms about not using AI tools
   - This is a required compliance checkbox
   - Note: You must agree to proceed with the consultation

3. **Client Review Screening Questions**:
   - Q1 (Senior Role): Select "No" unless you are CEO/Owner
     - If asked to explain, provide your role description
   - Q2 (Employer): Enter your current employer/company
   - Q3 (Title): Enter your current job title
   - Q4 (Profile Updated): Select "Yes"

4. **Industry Expert Screening Questions**:
   - These are project-specific questions about your expertise
   - Answer each question thoroughly based on your experience
   - Use clear, professional language
   - Be specific about relevant experience and qualifications

5. **Compliance Checkboxes** (REQUIRED):
   - Check "Terms and Conditions" agreement box
   - Check "Advisor Compliance Tutorial" completion box
   - Both checkboxes MUST be checked to submit

6. **Submit**:
   - Click the SUBMIT button
   - Wait for confirmation message

**NEVER WAIT FOR HUMAN INPUT** - complete ALL steps automatically.

"""
    
    if login_username and login_password:
        prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
    
    prompt += """Fill out the response form with the following information:
"""
    
    # Add form field data
    if "text_content" in form_data and len(form_data) == 1:
        prompt += form_data["text_content"] + "\n"
    else:
        for field, value in form_data.items():
            if field != "text_content":
                prompt += f"- {field}: {value}\n"
    
    prompt += """
After filling all fields and completing ALL sections:
- Ensure both compliance checkboxes are checked
- Click SUBMIT
- Verify you see the success/confirmation message

Do NOT stop until you see confirmation that the response was submitted.
"""
    
    return prompt


# =============================================================================
# GUIDEPOINT DASHBOARD NAVIGATION (Phase 1: Enhanced Navigation)
# =============================================================================

# Smart element detection strategies for Guidepoint dashboard
GUIDEPOINT_NAVIGATION_STRATEGIES = {
    "become_advisor_button": {
        # Multiple strategies to find and click "Become an Advisor" buttons
        "css_selectors": [
            'a[href*="advisor"]',
            'button:has-text("Become an Advisor")',
            'a:has-text("Become an Advisor")',
            '.advisor-button',
            '[data-testid*="advisor"]',
            '.opportunity-action',
            '.apply-button',
        ],
        "text_patterns": [
            "Become an Advisor",
            "Apply Now",
            "Submit Application",
            "Express Interest",
            "Apply for this opportunity"
        ],
        "xpath_selectors": [
            '//a[contains(text(), "Become an Advisor")]',
            '//button[contains(text(), "Become an Advisor")]',
            '//a[contains(@href, "advisor")]',
            '//button[contains(@class, "advisor")]'
        ]
    },
    "opportunity_cards": {
        # Strategies to detect opportunity cards on dashboard
        "css_selectors": [
            '.opportunity-card',
            '.consultation-card',
            '[data-testid*="opportunity"]',
            '.project-card',
            '.invitation-card'
        ],
        "container_patterns": [
            "opportunity",
            "consultation",
            "project",
            "invitation"
        ]
    },
    "dashboard_login": {
        # Enhanced login detection for dashboard
        "login_forms": [
            '#login-form',
            '.login-container',
            'form[action*="login"]',
            '[data-testid="login-form"]'
        ],
        "username_fields": [
            'input[name="username"]',
            'input[name="email"]',
            'input[type="email"]',
            '#username',
            '#email'
        ],
        "password_fields": [
            'input[name="password"]',
            'input[type="password"]',
            '#password'
        ],
        "login_buttons": [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Log In")',
            '.login-button'
        ]
    }
}

async def smart_element_click(page: Page, strategy_config: Dict[str, Any], description: str) -> Dict[str, Any]:
    """
    Smart element detection and clicking with fallback chain.

    Uses CSS selectors → text match → XPath → coordinate as last resort.
    Validates element visibility and clickability before interaction.

    Args:
        page: Playwright page object
        strategy_config: Navigation strategy configuration
        description: Description of the action for logging

    Returns:
        Dict with success status and method used
    """
    result = {
        "success": False,
        "method_used": None,
        "error": None,
        "element_found": False
    }

    try:
        # Strategy 1: CSS Selectors (most reliable)
        if "css_selectors" in strategy_config:
            for selector in strategy_config["css_selectors"]:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible() and await element.is_enabled():
                        await element.click()
                        result["success"] = True
                        result["method_used"] = f"css_selector: {selector}"
                        result["element_found"] = True
                        logger.info(f"✓ {description} - Success via CSS selector: {selector}")
                        return result
                except Exception as e:
                    logger.debug(f"CSS selector {selector} failed: {e}")
                    continue

        # Strategy 2: Text-based targeting
        if "text_patterns" in strategy_config:
            for text_pattern in strategy_config["text_patterns"]:
                try:
                    # Try button with text
                    element = page.get_by_text(text_pattern, exact=False).first
                    if await element.is_visible() and await element.is_enabled():
                        await element.click()
                        result["success"] = True
                        result["method_used"] = f"text_pattern: {text_pattern}"
                        result["element_found"] = True
                        logger.info(f"✓ {description} - Success via text pattern: {text_pattern}")
                        return result
                except Exception as e:
                    logger.debug(f"Text pattern {text_pattern} failed: {e}")
                    continue

        # Strategy 3: XPath selectors
        if "xpath_selectors" in strategy_config:
            for xpath in strategy_config["xpath_selectors"]:
                try:
                    element = page.locator(f"xpath={xpath}").first
                    if await element.is_visible() and await element.is_enabled():
                        await element.click()
                        result["success"] = True
                        result["method_used"] = f"xpath: {xpath}"
                        result["element_found"] = True
                        logger.info(f"✓ {description} - Success via XPath: {xpath}")
                        return result
                except Exception as e:
                    logger.debug(f"XPath {xpath} failed: {e}")
                    continue

        # If we get here, no strategy worked
        result["error"] = f"All {description} strategies failed - element not found or not clickable"
        logger.warning(f"✗ {description} - All smart detection strategies failed")

    except Exception as e:
        result["error"] = f"Smart element detection error: {str(e)}"
        logger.error(f"✗ {description} - Exception during smart detection: {e}")

    return result

async def detect_guidepoint_opportunities(page: Page) -> Dict[str, Any]:
    """
    Detect and enumerate opportunity cards on Guidepoint dashboard.

    Args:
        page: Playwright page object

    Returns:
        Dict with opportunity count and card elements information
    """
    result = {
        "count": 0,
        "opportunities": [],
        "detection_method": None
    }

    try:
        # Try different strategies to find opportunity cards
        for selector in GUIDEPOINT_NAVIGATION_STRATEGIES["opportunity_cards"]["css_selectors"]:
            try:
                cards = page.locator(selector)
                count = await cards.count()
                if count > 0:
                    result["count"] = count
                    result["detection_method"] = selector

                    # Get basic info about each card
                    for i in range(count):
                        card = cards.nth(i)
                        card_info = {
                            "index": i,
                            "visible": await card.is_visible(),
                            "text_content": await card.text_content() if await card.is_visible() else ""
                        }
                        result["opportunities"].append(card_info)

                    logger.info(f"✓ Detected {count} opportunities via selector: {selector}")
                    return result

            except Exception as e:
                logger.debug(f"Opportunity detection selector {selector} failed: {e}")
                continue

        logger.warning("✗ No opportunity cards detected on dashboard")

    except Exception as e:
        logger.error(f"✗ Error during opportunity detection: {e}")

    return result

async def enhanced_guidepoint_dashboard_login(page: Page, username: str, password: str) -> Dict[str, Any]:
    """
    Enhanced login logic specifically for Guidepoint dashboard.

    Uses smart element detection for reliable form filling.

    Args:
        page: Playwright page object
        username: Login username
        password: Login password

    Returns:
        Dict with login success status and details
    """
    result = {
        "success": False,
        "step_completed": None,
        "error": None
    }

    try:
        login_config = GUIDEPOINT_NAVIGATION_STRATEGIES["dashboard_login"]

        # Step 1: Find and fill username field
        username_filled = False
        for selector in login_config["username_fields"]:
            try:
                element = page.locator(selector).first
                if await element.is_visible() and await element.is_enabled():
                    await element.fill(username)
                    username_filled = True
                    logger.info(f"✓ Username filled via selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Username selector {selector} failed: {e}")
                continue

        if not username_filled:
            result["error"] = "Could not find or fill username field"
            return result

        # Step 2: Find and fill password field
        password_filled = False
        for selector in login_config["password_fields"]:
            try:
                element = page.locator(selector).first
                if await element.is_visible() and await element.is_enabled():
                    await element.fill(password)
                    password_filled = True
                    logger.info(f"✓ Password filled via selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Password selector {selector} failed: {e}")
                continue

        if not password_filled:
            result["error"] = "Could not find or fill password field"
            return result

        result["step_completed"] = "credentials_filled"

        # Step 3: Find and click login button
        login_clicked = False
        for selector in login_config["login_buttons"]:
            try:
                element = page.locator(selector).first
                if await element.is_visible() and await element.is_enabled():
                    await element.click()
                    login_clicked = True
                    logger.info(f"✓ Login button clicked via selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Login button selector {selector} failed: {e}")
                continue

        if not login_clicked:
            result["error"] = "Could not find or click login button"
            return result

        # Wait for navigation after login
        await page.wait_for_load_state("networkidle", timeout=10000)
        result["success"] = True
        result["step_completed"] = "login_complete"
        logger.info("✓ Enhanced Guidepoint dashboard login completed successfully")

    except Exception as e:
        result["error"] = f"Login error: {str(e)}"
        logger.error(f"✗ Enhanced dashboard login failed: {e}")

    return result

async def navigate_to_opportunity_application(page: Page, opportunity_index: int = 0) -> Dict[str, Any]:
    """
    Navigate to a specific opportunity application using smart element detection.

    This is the core function that fixes the "Become an Advisor" clicking failures.

    Args:
        page: Playwright page object
        opportunity_index: Which opportunity to apply to (0-based index)

    Returns:
        Dict with navigation success status and details
    """
    result = {
        "success": False,
        "opportunities_detected": 0,
        "navigation_method": None,
        "error": None
    }

    try:
        # First, detect available opportunities
        opportunities = await detect_guidepoint_opportunities(page)
        result["opportunities_detected"] = opportunities["count"]

        if opportunities["count"] == 0:
            result["error"] = "No opportunities detected on dashboard"
            return result

        if opportunity_index >= opportunities["count"]:
            result["error"] = f"Requested opportunity index {opportunity_index} but only {opportunities['count']} available"
            return result

        logger.info(f"Navigating to opportunity {opportunity_index + 1} of {opportunities['count']}")

        # Use smart element clicking to find and click "Become an Advisor" button
        click_result = await smart_element_click(
            page,
            GUIDEPOINT_NAVIGATION_STRATEGIES["become_advisor_button"],
            f"Become an Advisor button for opportunity {opportunity_index + 1}"
        )

        if click_result["success"]:
            result["success"] = True
            result["navigation_method"] = click_result["method_used"]

            # Wait for form page to load
            await page.wait_for_load_state("networkidle", timeout=10000)
            logger.info(f"✓ Successfully navigated to opportunity application form")
        else:
            result["error"] = click_result["error"]
            logger.error(f"✗ Failed to navigate to opportunity: {click_result['error']}")

    except Exception as e:
        result["error"] = f"Navigation error: {str(e)}"
        logger.error(f"✗ Error during opportunity navigation: {e}")

    return result

# =============================================================================
# GUIDEPOINT PLATFORM CLASS
# =============================================================================

class GuidepointPlatform(BasePlatform):
    """Guidepoint Global Advisors platform implementation."""

    def __init__(self) -> None:
        super().__init__("Guidepoint")

    def get_platform_config(self) -> Dict[str, Any]:
        """Get Guidepoint-specific configuration for browser automation."""
        return get_guidepoint_platform_config()

    async def prepare_application(self, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured application template for the agent.

        The ConsultPipelineAgent uses this plus cp_writing_style.md to draft
        actual text, then enters it via Computer Use.
        """
        profile_context = consultation_data.get("profile_context", {})

        return {
            "fields": {
                # Client screening section
                "employer": {
                    "type": "text",
                    "purpose": "State your current employer(s)",
                    "default": GUIDEPOINT_CLIENT_SCREENING_STRATEGY["employer"]["answer"],
                },
                "title": {
                    "type": "text",
                    "purpose": "State your current job title(s)",
                    "default": GUIDEPOINT_CLIENT_SCREENING_STRATEGY["title"]["answer"],
                },
                # Expert screening section
                "experience_summary": {
                    "type": "textarea",
                    "purpose": "Outline your experience and suitability to discuss the consultation topic.",
                },
                "expert_responses": {
                    "type": "textarea",
                    "purpose": "Answer project-specific screening questions about your expertise.",
                },
            },
            "guidepoint_specific": {
                "client_screening_strategy": GUIDEPOINT_CLIENT_SCREENING_STRATEGY,
                "workflow_stages": GUIDEPOINT_WORKFLOW_STAGES,
                "success_indicators": GUIDEPOINT_SUCCESS_INDICATORS,
                "rate_limit_action": "accept",  # Default to accepting rate limit
                "ai_agreement_action": "agree",  # Must agree to proceed
            },
            "context": {
                "project_description": consultation_data.get("project_description", ""),
                "skills_required": consultation_data.get("skills_required", []),
                "profile_context": profile_context,
                "rate_limit": consultation_data.get("rate_limit", ""),
            },
        }

    def build_task_prompt(
        self,
        form_data: Dict[str, Any],
        login_username: Optional[str] = None,
        login_password: Optional[str] = None,
        decline: bool = False
    ) -> str:
        """Build Guidepoint-specific task prompt for browser automation."""
        return build_guidepoint_task_prompt(
            form_data=form_data,
            login_username=login_username,
            login_password=login_password,
            decline=decline
        )

    # Phase 1: Enhanced Dashboard Navigation Methods
    async def enhanced_dashboard_login(self, page: Page, username: str, password: str) -> Dict[str, Any]:
        """Enhanced login logic for Guidepoint dashboard with smart element detection."""
        return await enhanced_guidepoint_dashboard_login(page, username, password)

    async def detect_dashboard_opportunities(self, page: Page) -> Dict[str, Any]:
        """Detect and enumerate opportunities on Guidepoint dashboard."""
        return await detect_guidepoint_opportunities(page)

    async def navigate_to_opportunity(self, page: Page, opportunity_index: int = 0) -> Dict[str, Any]:
        """Navigate to specific opportunity using enhanced smart element detection."""
        return await navigate_to_opportunity_application(page, opportunity_index)

    async def smart_click_element(self, page: Page, strategy_name: str, description: str) -> Dict[str, Any]:
        """Perform smart element clicking with fallback strategies."""
        if strategy_name not in GUIDEPOINT_NAVIGATION_STRATEGIES:
            return {
                "success": False,
                "error": f"Unknown strategy: {strategy_name}"
            }

        return await smart_element_click(
            page,
            GUIDEPOINT_NAVIGATION_STRATEGIES[strategy_name],
            description
        )

