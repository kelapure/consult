"""Coleman (VISASQ/Coleman) platform implementation.

This module contains ALL Coleman-specific code:
- Dialog handling (cookie consent, popups)
- Success/failure/blocked indicators
- Form field templates with answering strategies
- Workflow stages for multi-step vetting Q&A
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
# COLEMAN-SPECIFIC SUCCESS/FAILURE/BLOCKED INDICATORS
# =============================================================================

COLEMAN_SUCCESS_INDICATORS = [
    # Coleman-specific success messages (from actual workflow)
    "you're all set",
    "you're all set!",
    "wait for your research manager",
    "thank you for completing",
    "vetting complete",
    "response submitted",
    "successfully submitted",
    "thank you for your response",
    "your response has been recorded",
    "submission complete",
    "thanks for completing",
]

COLEMAN_FAILURE_INDICATORS = [
    # Coleman-specific failure messages
    "an error occurred",
    "something went wrong",
    "could not submit",
    "unable to process",
    "submission failed",
    "please try again",
]

COLEMAN_BLOCKED_INDICATORS = [
    # Coleman-specific blocked states
    "already completed",
    "request expired",
    "vetting closed",
    "no longer available",
    "request is closed",
    "already responded",
]


# =============================================================================
# COLEMAN-SPECIFIC WORKFLOW STAGES
# =============================================================================

COLEMAN_WORKFLOW_STAGES = {
    # Actual Coleman workflow stages from screenshots
    "vetting_questions": ["provide your thoughts", "subject matter", "vetting q&a", "answer questions"],
    "rate_limit": ["rate limit", "$0 - $1000", "per hour", "all good"],
    "complete_vetting": ["complete vetting", "submit & continue"],
    "completion": ["you're all set", "wait for your research manager", "vetting complete"],
}


# =============================================================================
# COLEMAN-SPECIFIC DIALOG SELECTORS
# =============================================================================

# Generic cookie consent banner (Coleman may use various providers)
COLEMAN_COOKIE_DIALOG = {
    "dialog_selectors": [
        '[class*="cookie"]',
        '[id*="cookie"]',
        '[class*="consent"]',
        '.cookie-banner',
        '#cookie-banner',
    ],
    "dismiss_selectors": [
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("OK")',
        'button:has-text("I Agree")',
        'button:has-text("Got it")',
        '[class*="accept"]',
    ],
    "description": "Coleman cookie consent banner"
}

# Additional Coleman cookie button selectors (for core cookie detection)
COLEMAN_COOKIE_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("OK")',
    'button:has-text("I Agree")',
]


# =============================================================================
# COLEMAN-SPECIFIC FORM FIELD TEMPLATES
# =============================================================================

# Default responses for common vetting questions
COLEMAN_VETTING_DEFAULTS = {
    # Expertise confirmation
    "expertise_relevant": {
        "answer": "Yes",
        "keywords": ["relevant", "expertise", "experience", "background"],
    },
    # Availability confirmation
    "available": {
        "answer": "Yes",
        "keywords": ["available", "schedule", "timing"],
    },
    # Default for unknown questions
    "default": {
        "answer": "Yes",
    },
}


# =============================================================================
# COLEMAN DIALOG HANDLER
# =============================================================================

async def dismiss_coleman_cookie_banner(page: Page) -> bool:
    """
    Dismiss Coleman's cookie consent banner.

    Args:
        page: Playwright page object

    Returns:
        True if banner was found and dismissed, False otherwise
    """
    return await dismiss_dialog_by_selectors(
        page,
        dialog_selectors=COLEMAN_COOKIE_DIALOG["dialog_selectors"],
        dismiss_selectors=COLEMAN_COOKIE_DIALOG["dismiss_selectors"],
        description=COLEMAN_COOKIE_DIALOG["description"]
    )


async def dismiss_all_coleman_dialogs(page: Page, max_iterations: int = 3) -> Dict[str, Any]:
    """
    Dismiss all known Coleman-specific dialogs in sequence.

    This is the main entry point for Coleman dialog handling. It handles:
    - Cookie consent banners
    - Any other persistent dialogs

    Args:
        page: Playwright page object
        max_iterations: Maximum iterations to handle persistent dialogs

    Returns:
        Dict with results for each dialog type:
        {
            "cookie_banner": bool,
            "iterations": int
        }
    """
    results = {
        "cookie_banner": False,
        "iterations": 0
    }

    for iteration in range(max_iterations):
        results["iterations"] = iteration + 1
        dismissed_any = False

        # Try cookie banner
        if not results["cookie_banner"]:
            if await dismiss_coleman_cookie_banner(page):
                results["cookie_banner"] = True
                dismissed_any = True
                await asyncio.sleep(0.3)

        # If nothing was dismissed, we're done
        if not dismissed_any:
            break

        logger.debug(f"Coleman dialog dismissal iteration {iteration + 1}: {results}")

    return results


# =============================================================================
# COLEMAN DASHBOARD HANDLERS
# =============================================================================

async def navigate_to_coleman_opportunity(
    page: Page,
    index: int = 0,
    correlation_id: str = "N/A"
) -> bool:
    """
    Navigate to a specific Coleman opportunity (vetting Q&A).
    
    Uses smart_element_click for robust button detection.
    
    Args:
        page: Playwright page object
        index: Index of the opportunity to navigate to (0-based)
        correlation_id: Optional ID for logging context
        
    Returns:
        True if navigation succeeded, False otherwise
    """
    try:
        # Coleman-specific button strategies
        vetting_strategies = [
            {"type": "text", "selector": 'button:has-text("Complete Vetting Q&A")', "description": "Complete Vetting button"},
            {"type": "text", "selector": 'a:has-text("Complete Vetting Q&A")', "description": "Complete Vetting link"},
            {"type": "css", "selector": '[class*="btn"]:has-text("Complete Vetting")', "description": "Vetting button by class"},
            {"type": "text", "selector": 'button:has-text("Start")', "description": "Start button"},
            {"type": "text", "selector": 'a:has-text("Start")', "description": "Start link"},
        ]
        
        # Try to find all matching elements and click the one at index
        for strategy in vetting_strategies:
            try:
                selector = strategy["selector"]
                if strategy["type"] == "css":
                    elements = await page.query_selector_all(selector)
                else:
                    # Use locator for text selectors
                    locator = page.locator(selector)
                    count = await locator.count()
                    elements = []
                    for i in range(count):
                        try:
                            el = await locator.nth(i).element_handle()
                            if el:
                                elements.append(el)
                        except Exception:
                            continue
                
                # Filter for visible elements
                visible_elements = []
                for el in elements:
                    try:
                        if el and await el.is_visible():
                            visible_elements.append(el)
                    except Exception:
                        continue
                
                if visible_elements and index < len(visible_elements):
                    await visible_elements[index].click()
                    logger.info(f"[{correlation_id}] Coleman: Clicked vetting button {index + 1} via {strategy['description']}")
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                logger.debug(f"[{correlation_id}] Coleman navigation strategy failed: {strategy['description']} - {e}")
                continue
        
        # Fallback: use smart_element_click for first opportunity
        if index == 0:
            clicked = await smart_element_click(page, vetting_strategies, correlation_id)
            if clicked:
                await asyncio.sleep(2)
                return True
        
        # Last fallback: search all buttons by text
        try:
            buttons = await page.query_selector_all('button, a.btn, [role="button"]')
            matching_buttons = []
            for btn in buttons:
                try:
                    text = await btn.inner_text()
                    if 'complete vetting' in text.lower() or 'start survey' in text.lower():
                        if await btn.is_visible():
                            matching_buttons.append(btn)
                except Exception:
                    continue
            
            if matching_buttons and index < len(matching_buttons):
                await matching_buttons[index].click()
                logger.info(f"[{correlation_id}] Coleman: Clicked button {index + 1} via text search fallback")
                await asyncio.sleep(2)
                return True
        except Exception as e:
            logger.debug(f"[{correlation_id}] Coleman text search fallback failed: {e}")
        
        logger.warning(f"[{correlation_id}] Coleman: Could not navigate to opportunity {index + 1}")
        return False
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Coleman navigation error: {e}")
        return False


async def detect_coleman_opportunities(
    page: Page,
    correlation_id: str = "N/A"
) -> int:
    """
    Detect the number of Coleman vetting opportunities on the dashboard.
    
    Args:
        page: Playwright page object
        correlation_id: Optional ID for logging context
        
    Returns:
        Number of opportunities detected
    """
    try:
        # Count "Complete Vetting Q&A" buttons
        buttons = await page.query_selector_all('button, a.btn, [role="button"]')
        coleman_count = 0
        for btn in buttons:
            try:
                text = await btn.inner_text()
                if 'complete vetting' in text.lower():
                    coleman_count += 1
            except Exception:
                continue
        
        if coleman_count > 0:
            logger.info(f"[{correlation_id}] Coleman: Found {coleman_count} vetting opportunities")
            return coleman_count
        
        # Fallback: check for project cards or to-do items
        try:
            cards = await page.query_selector_all('.project-card, [class*="to-do"], [class*="todo"]')
            if cards:
                logger.info(f"[{correlation_id}] Coleman: Found {len(cards)} project cards")
                return len(cards)
        except Exception:
            pass
        
        logger.warning(f"[{correlation_id}] Coleman: Could not determine opportunity count")
        return 0
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Coleman opportunity detection error: {e}")
        return 0


def get_coleman_platform_config() -> Dict[str, Any]:
    """
    Get the platform configuration for Coleman.

    This configuration is passed to BrowserAutomation to enable
    Coleman-specific behavior without hardcoding it in the core module.

    Returns:
        Platform configuration dict for BrowserAutomation
    """
    return {
        "success_indicators": COLEMAN_SUCCESS_INDICATORS,
        "failure_indicators": COLEMAN_FAILURE_INDICATORS,
        "blocked_indicators": COLEMAN_BLOCKED_INDICATORS,
        "workflow_stages": COLEMAN_WORKFLOW_STAGES,
        "dialog_handler": dismiss_all_coleman_dialogs,
        "cookie_selectors": COLEMAN_COOKIE_SELECTORS,
        # Platform-specific handlers for decoupled browser automation
        "opportunity_navigator": navigate_to_coleman_opportunity,
        "opportunity_detector": detect_coleman_opportunities,
        # Coleman dashboard invitations are pre-filtered by the platform
        # Always accept since they're already relevant to the expert
        "always_accept_dashboard_invitations": True,
    }


# =============================================================================
# COLEMAN TASK PROMPT GENERATION
# =============================================================================

def build_coleman_task_prompt(
    form_data: Dict[str, Any],
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    decline: bool = False
) -> str:
    """
    Build a Coleman-specific task prompt for browser automation.

    This generates detailed instructions for the AI to complete
    Coleman's multi-step vetting Q&A form.

    Args:
        form_data: Form field data to fill
        login_username: Coleman username if login needed
        login_password: Coleman password if login needed
        decline: Whether to decline instead of accept

    Returns:
        Complete task prompt string
    """
    if decline:
        prompt = """DECLINE the Coleman/VISASQ consultation opportunity.

"""
        if login_username and login_password:
            prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
        prompt += """Navigate to the project and click the "Decline Vetting Q&A" button.
Confirm the decline action if prompted.
"""
        return prompt

    # Accept workflow - Complete Vetting Q&A
    prompt = """Complete the Coleman/VISASQ Vetting Q&A form.

**CRITICAL - COLEMAN MULTI-STEP WORKFLOW:**
Coleman vetting has multiple steps. You MUST complete ALL steps:

1. **Navigate to Dashboard**:
   - Go to the To-Do list at https://experts.coleman.colemanerm.com/#!/expert/to-do
   - Find the project card you want to complete

2. **Click "Complete Vetting Q&A"**:
   - This opens the vetting questionnaire

3. **Step 1 - Vetting Questions**:
   - You'll see a textarea asking "Please provide your thoughts on the subject matter"
   - Provide detailed, professional response about the topic
   - Use CP writing style: direct, confident, data-driven
   - Click "SUBMIT & CONTINUE" button

4. **Step 2 - Rate Limit Confirmation**:
   - You'll see "Rate Limit" section showing "$0 - $1000 per hour"
   - Click the "All Good" checkbox/button to confirm the rate
   - Click "COMPLETE VETTING" button

5. **Completion**:
   - Verify you see "You're all set!" confirmation message
   - You should see "Wait for your Research Manager..." text

**NEVER WAIT FOR HUMAN INPUT** - complete ALL steps automatically.

"""

    if login_username and login_password:
        prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""

    prompt += """Fill out the vetting form with the following information:
"""

    # Add form field data
    if "text_content" in form_data and len(form_data) == 1:
        prompt += form_data["text_content"] + "\n"
    else:
        for field, value in form_data.items():
            if field != "text_content":
                prompt += f"- {field}: {value}\n"

    prompt += """
After completing all steps (vetting questions + rate limit confirmation),
verify you see the "You're all set!" confirmation message.
"""

    return prompt


# =============================================================================
# COLEMAN PLATFORM CLASS
# =============================================================================

class ColemanPlatform(BasePlatform):
    """Coleman (VISASQ/Coleman) platform implementation."""

    def __init__(self) -> None:
        super().__init__("Coleman")

    def get_platform_config(self) -> Dict[str, Any]:
        """Get Coleman-specific configuration for browser automation."""
        return get_coleman_platform_config()

    async def prepare_application(self, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured application template for the agent.

        The ConsultPipelineAgent uses this plus cp_writing_style.md to draft
        actual text, then enters it via Computer Use.
        """
        profile_context = consultation_data.get("profile_context", {})

        return {
            "fields": {
                "thoughts_on_subject": {
                    "type": "textarea",
                    "purpose": "Provide your thoughts on the subject matter - professional insights, relevant experience, and perspective on the topic.",
                },
                "rate_limit_confirmation": {
                    "type": "checkbox",
                    "purpose": "Confirm the rate limit ($0-$1000/hour) by clicking 'All Good'.",
                    "default": "All Good",
                },
            },
            "coleman_specific": {
                "vetting_defaults": COLEMAN_VETTING_DEFAULTS,
                "workflow_stages": COLEMAN_WORKFLOW_STAGES,
                "success_indicators": COLEMAN_SUCCESS_INDICATORS,
            },
            "context": {
                "project_description": consultation_data.get("project_description", ""),
                "skills_required": consultation_data.get("skills_required", []),
                "profile_context": profile_context,
            },
        }

    def build_task_prompt(
        self,
        form_data: Dict[str, Any],
        login_username: Optional[str] = None,
        login_password: Optional[str] = None,
        decline: bool = False
    ) -> str:
        """Build Coleman-specific task prompt for browser automation."""
        return build_coleman_task_prompt(
            form_data=form_data,
            login_username=login_username,
            login_password=login_password,
            decline=decline
        )
