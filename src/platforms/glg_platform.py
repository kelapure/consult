"""GLG platform implementation.

This module contains ALL GLG-specific code:
- Dialog handling (China location, OneTrust cookies)
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


# =============================================================================
# GLG-SPECIFIC SUCCESS/FAILURE/BLOCKED INDICATORS
# =============================================================================

GLG_SUCCESS_INDICATORS = [
    # GLG-specific success messages
    "thanks, you're all set",
    "thanks, you're all set!",
    "application received",
    "we'll reach out",
    "you have applied",
    "your application has been submitted",
    "you're all set",
]

GLG_FAILURE_INDICATORS = [
    # GLG-specific failure messages
    "you have already declined",
    "already declined the project",
    "project is no longer available",
    "cannot apply to this project",
]

GLG_BLOCKED_INDICATORS = [
    # GLG-specific blocked states
    "already declined",
    "already applied",
    "project expired",
    "invitation has expired",
    "you have already declined",
]


# =============================================================================
# GLG-SPECIFIC WORKFLOW STAGES (Enhanced for Agent Recognition)
# =============================================================================

GLG_WORKFLOW_STAGES = {
    "product_familiarity": {
        "patterns": ["familiarity", "experience with", "which products", "your familiarity"],
        "action_guidance": "Select appropriate familiarity level based on profile knowledge",
        "success_indicators": ["radio button selected", "checkbox checked", "next button enabled"]
    },
    "additional_info": {
        "patterns": ["additional comments", "tell us more", "provide details", "anything else"],
        "action_guidance": "Fill textarea with professional background summary",
        "success_indicators": ["text entered", "character count updated", "field validation passed"]
    },
    "phone_selection": {
        "patterns": ["phone number", "contact number", "best number", "reach you"],
        "action_guidance": "Select the cell phone option from dropdown",
        "success_indicators": ["phone option selected", "dropdown closed", "next enabled"]
    },
    "rate_setting": {
        "patterns": ["project rate", "hourly rate", "set your rate", "rate for this"],
        "action_guidance": "Confirm $500/hour rate setting",
        "success_indicators": ["rate confirmed", "set project rate clicked", "rate saved"]
    },
    "terms_acknowledgment": {
        "patterns": ["terms and conditions", "acknowledge", "i confirm", "bound by"],
        "action_guidance": "Check acknowledgment checkbox then click Apply",
        "success_indicators": ["checkbox checked", "apply button enabled", "terms accepted"]
    },
    "availability": {
        "patterns": ["availability", "add availability", "schedule", "when are you available"],
        "action_guidance": "Click Add Availability, select slots, Save, then Proceed",
        "success_indicators": ["slots selected", "availability saved", "proceed clicked"]
    },
    "final_submit": {
        "patterns": ["apply for this project", "submit application", "confirm & submit"],
        "action_guidance": "Click final submit button to complete application",
        "success_indicators": ["application submitting", "loading indicator", "processing"]
    },
    "completion": {
        "patterns": ["thanks, you're all set", "all set", "you're all set", "application received"],
        "action_guidance": "TASK COMPLETE - application successfully submitted",
        "success_indicators": ["success message visible", "completion page loaded", "task finished"]
    }
}


# =============================================================================
# GLG-SPECIFIC DIALOG SELECTORS
# =============================================================================

# China location question dialog
GLG_CHINA_DIALOG = {
    "dialog_selectors": [
        '[role="dialog"]:has-text("China")',
        '.MuiDialog-root:has-text("China")',
        '[class*="dialog"]:has-text("based in China")',
        '[class*="Dialog"]:has-text("China")',
    ],
    "dismiss_selectors": [
        'button:has-text("No")',
        'button:has-text("NO")',
        '[aria-label="No"]',
        '.MuiButton-root:has-text("No")',
    ],
    "description": "GLG China location dialog"
}

# OneTrust cookie consent banner (GLG uses this)
GLG_ONETRUST_COOKIE = {
    "dialog_selectors": [
        '#onetrust-banner-sdk',
        '.onetrust-pc-dark-filter',
        '[class*="onetrust"]',
    ],
    "dismiss_selectors": [
        '#onetrust-accept-btn-handler',
        'button:has-text("Allow All Cookies")',
        'button:has-text("Accept All")',
        '#onetrust-pc-btn-handler',
        'button:has-text("Confirm My Choice")',
    ],
    "description": "GLG OneTrust cookie banner"
}

# Additional GLG cookie button selectors (for core cookie detection)
GLG_COOKIE_SELECTORS = [
    '#onetrust-accept-btn-handler',
    'button:has-text("Allow All Cookies")',
    'button:has-text("Confirm My Choice")',
]


# =============================================================================
# GLG-SPECIFIC FORM FIELD TEMPLATES
# =============================================================================

# Product familiarity answering strategy based on profile
GLG_PRODUCT_FAMILIARITY_STRATEGY = {
    # Google products - select "4 - My company is offering to customers"
    "google": {
        "answer": "4",
        "keywords": ["google", "gcp", "gemini", "cloud", "bigquery", "vertex"],
    },
    # Competitor products - select "3 - Evaluated, not offering as a product"
    "evaluated": {
        "answer": "3",
        "keywords": ["amazon", "aws", "microsoft", "azure", "salesforce"],
    },
    # Unknown products - select "2 - Aware, not evaluated"
    "default": {
        "answer": "2",
    },
}


# =============================================================================
# GLG DIALOG HANDLER
# =============================================================================

async def dismiss_glg_china_dialog(page: Page) -> bool:
    """
    Dismiss GLG's "Are you based in China?" location dialog.

    GLG shows this dialog to determine regional compliance requirements.
    For most users, clicking "No" is the correct action.

    Args:
        page: Playwright page object

    Returns:
        True if dialog was found and dismissed, False otherwise
    """
    return await dismiss_dialog_by_selectors(
        page,
        dialog_selectors=GLG_CHINA_DIALOG["dialog_selectors"],
        dismiss_selectors=GLG_CHINA_DIALOG["dismiss_selectors"],
        description=GLG_CHINA_DIALOG["description"]
    )


async def dismiss_glg_cookie_banner(page: Page) -> bool:
    """
    Dismiss GLG's OneTrust cookie consent banner.

    GLG uses OneTrust for cookie consent. This function specifically
    handles GLG's implementation including the preferences modal.

    Args:
        page: Playwright page object

    Returns:
        True if banner was found and dismissed, False otherwise
    """
    return await dismiss_dialog_by_selectors(
        page,
        dialog_selectors=GLG_ONETRUST_COOKIE["dialog_selectors"],
        dismiss_selectors=GLG_ONETRUST_COOKIE["dismiss_selectors"],
        description=GLG_ONETRUST_COOKIE["description"]
    )


async def dismiss_all_glg_dialogs(page: Page, max_iterations: int = 5) -> Dict[str, Any]:
    """
    Dismiss all known GLG-specific dialogs in sequence.

    This is the main entry point for GLG dialog handling. It handles:
    - Cookie consent (OneTrust)
    - China location question
    - Any other persistent dialogs

    Args:
        page: Playwright page object
        max_iterations: Maximum iterations to handle persistent dialogs

    Returns:
        Dict with results for each dialog type:
        {
            "cookie_banner": bool,
            "china_dialog": bool,
            "iterations": int
        }
    """
    results = {
        "cookie_banner": False,
        "china_dialog": False,
        "iterations": 0
    }

    for iteration in range(max_iterations):
        results["iterations"] = iteration + 1
        dismissed_any = False

        # 1. Try cookie banner first (often appears on top)
        if not results["cookie_banner"]:
            if await dismiss_glg_cookie_banner(page):
                results["cookie_banner"] = True
                dismissed_any = True
                await asyncio.sleep(0.3)

        # 2. Try China location dialog
        if await dismiss_glg_china_dialog(page):
            results["china_dialog"] = True
            dismissed_any = True
            await asyncio.sleep(0.3)

        # If nothing was dismissed, we're done
        if not dismissed_any:
            break

        logger.debug(f"GLG dialog dismissal iteration {iteration + 1}: {results}")

    return results


async def handle_glg_decline_dialog(page: Page) -> bool:
    """
    Robust GLG decline dialog handler that prevents the iteration 30 failure.

    This specifically handles the decline confirmation dialog that caused the
    10-minute stall in the Nov 30 GLG run. Uses precise element targeting
    instead of coordinates to ensure reliable interaction.

    Returns:
        True if decline dialog was handled successfully, False if not found/failed
    """
    try:
        logger.info("GLG: Looking for decline confirmation dialog...")

        # Step 1: Wait for and detect the decline dialog
        # The iteration 30 failure was a MuiDialog that stayed open
        decline_dialog = None
        dialog_selectors = [
            '.MuiDialog-root',  # Material-UI dialog (from logs)
            '[role="dialog"]',  # Accessibility-based
            '.decline-dialog',
            '.confirm-dialog',
            'div[data-testid*="decline"]'
        ]

        for selector in dialog_selectors:
            try:
                decline_dialog = await page.wait_for_selector(selector, timeout=2000)
                if decline_dialog:
                    logger.info(f"GLG: Found decline dialog using selector: {selector}")
                    break
            except:
                continue

        if not decline_dialog:
            logger.debug("GLG: No decline dialog found")
            return False

        # Step 2: Handle decline reason selection (this is what failed at iteration 30)
        # Try multiple selectors for decline reasons
        decline_reason_selected = False
        reason_selectors = [
            'input[value="no-expertise"]',  # Direct value match
            'input[value*="expertise"]',    # Partial value match
            'input[type="radio"][value*="relevant"]',  # Radio button with "relevant"
            '[data-testid*="no-expertise"]',
            'label:has-text("don\'t have relevant expertise")',  # Text-based
            'label:has-text("relevant expertise")',
            '.MuiFormControlLabel-root:has-text("expertise")'  # Material-UI specific
        ]

        for reason_selector in reason_selectors:
            try:
                reason_option = page.locator(reason_selector)
                if await reason_option.count() > 0:
                    await reason_option.first.click(timeout=3000)
                    logger.info(f"GLG: Selected decline reason with: {reason_selector}")
                    decline_reason_selected = True
                    await asyncio.sleep(0.5)  # Let selection register
                    break
            except Exception as e:
                logger.debug(f"GLG: Reason selector failed: {reason_selector} - {e}")
                continue

        if not decline_reason_selected:
            logger.warning("GLG: Could not select decline reason, trying to submit anyway")

        # Step 3: Submit the decline dialog (this is what precisely failed at iteration 30)
        # The logs show coordinates [956, 499] failed but [991, 227] worked
        submit_success = False
        submit_selectors = [
            'button[type="submit"]',  # Standard submit button
            'button:has-text("Decline")',  # Text-based
            'button:has-text("Submit")',
            'button:has-text("Confirm")',
            '.MuiButton-root:has-text("Decline")',  # Material-UI specific
            '.MuiButton-root:has-text("Submit")',
            '[data-testid*="submit"]',
            '[data-testid*="decline-confirm"]',
            'button[aria-label*="decline"]',
            'button[aria-label*="submit"]'
        ]

        for submit_selector in submit_selectors:
            try:
                submit_button = page.locator(submit_selector)
                if await submit_button.count() > 0:
                    await submit_button.first.click(timeout=3000)
                    logger.info(f"GLG: Clicked decline submit with: {submit_selector}")
                    submit_success = True
                    break
            except Exception as e:
                logger.debug(f"GLG: Submit selector failed: {submit_selector} - {e}")
                continue

        if not submit_success:
            logger.error("GLG: Failed to submit decline dialog - this could cause iteration loops")
            return False

        # Step 4: Verify dialog actually closed (critical - this prevents iteration loops)
        dialog_closed = False
        try:
            # Wait for the dialog to disappear
            await page.wait_for_selector('.MuiDialog-root', state='hidden', timeout=5000)
            dialog_closed = True
            logger.info("GLG: Decline dialog successfully closed")
        except:
            # Try alternative verification - check if dialog is no longer visible
            try:
                dialog_still_visible = await page.locator('.MuiDialog-root').is_visible()
                if not dialog_still_visible:
                    dialog_closed = True
                    logger.info("GLG: Decline dialog no longer visible")
            except:
                pass

        if not dialog_closed:
            logger.error("GLG: Decline dialog still open after submit - iteration loop risk!")
            return False

        # Step 5: Verify we're back on the opportunities page (final confirmation)
        await asyncio.sleep(1)  # Let page settle
        try:
            # Look for indicators that we're back on the opportunities list
            back_on_list = False
            list_indicators = [
                'text="Viewing 1 of"',  # From logs: "Viewing 1 of 1 projects" after decline
                '.opportunity-list',
                '.projects-list',
                'text="projects"',
                'text="opportunities"'
            ]

            for indicator in list_indicators:
                try:
                    if await page.locator(indicator).count() > 0:
                        back_on_list = True
                        logger.info(f"GLG: Confirmed back on opportunities list: {indicator}")
                        break
                except:
                    continue

            if back_on_list:
                logger.success("GLG: Decline workflow completed successfully")
                return True
            else:
                logger.warning("GLG: Decline submitted but unclear if back on opportunities list")
                return True  # Assume success since dialog closed

        except Exception as e:
            logger.debug(f"GLG: List verification error: {e}")
            return True  # Assume success since dialog closed

    except Exception as e:
        logger.error(f"GLG: Decline dialog handler failed: {e}")
        return False


def get_glg_platform_config() -> Dict[str, Any]:
    """
    Get the platform configuration for GLG.

    This configuration is passed to BrowserAutomation to enable
    GLG-specific behavior without hardcoding it in the core module.

    NEW: Includes intelligent state machine for objective-based termination
    instead of iteration counting (fixes iteration 30 dialog failure).

    Returns:
        Platform configuration dict for BrowserAutomation
    """
    return {
        "success_indicators": GLG_SUCCESS_INDICATORS,
        "failure_indicators": GLG_FAILURE_INDICATORS,
        "blocked_indicators": GLG_BLOCKED_INDICATORS,
        "workflow_stages": GLG_WORKFLOW_STAGES,
        "dialog_handler": dismiss_all_glg_dialogs,
        "decline_dialog_handler": handle_glg_decline_dialog,  # Robust decline dialog handler
        "cookie_selectors": GLG_COOKIE_SELECTORS,

        # Enhanced agent guidance for intelligent decision-making within agentic loop
        "enable_intelligent_termination": True,  # Uses enhanced success detection patterns
    }


# =============================================================================
# GLG TASK PROMPT GENERATION
# =============================================================================

def build_glg_task_prompt(
    form_data: Dict[str, Any],
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    decline: bool = False
) -> str:
    """
    Build a GLG-specific task prompt for browser automation.
    
    This generates detailed instructions for the AI to complete
    GLG's multi-step application form.
    
    Args:
        form_data: Form field data to fill
        login_username: GLG username if login needed
        login_password: GLG password if login needed
        decline: Whether to decline instead of accept
        
    Returns:
        Complete task prompt string
    """
    if decline:
        prompt = """DECLINE the GLG consultation opportunity.

"""
        if login_username and login_password:
            prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
        prompt += """Navigate to the consultation details and initiate the decline process.

**ROBUST DECLINE WORKFLOW:**
1. **Find and click the DECLINE button** on the consultation page
2. **Handle the decline dialog carefully:**
   - Select a decline reason (typically "I don't have relevant expertise")
   - Click the Submit/Confirm button to complete the decline
   - VERIFY the dialog actually closes (critical for preventing loops)
   - VERIFY you return to the opportunities list showing one fewer project

**CRITICAL:** If the decline dialog appears to be stuck or doesn't close after clicking submit, try:
- Different decline reason selections
- Alternative submit button selectors
- JavaScript-based clicking as fallback

The decline must be completed successfully to avoid iteration loops.
"""
        return prompt
    
    # Accept workflow
    prompt = """Complete the GLG consultation application form using INTELLIGENT WORKFLOW RECOGNITION.

**AGENTIC DECISION-MAKING FRAMEWORK:**
You are an intelligent agent. Use these patterns to RECOGNIZE what stage you're in and DECIDE what action to take:

**WORKFLOW STAGE RECOGNITION (look for these patterns on each screenshot):**

1. **Product Familiarity Stage** - Look for: "familiarity", "experience with", "which products"
   → Action: Select appropriate familiarity level, check biography confirmation
   → Success: Radio buttons selected, next button enabled

2. **Additional Comments Stage** - Look for: "additional comments", "tell us more", "provide details"
   → Action: Fill textarea with professional background
   → Success: Text entered, field validation passed

3. **Phone Selection Stage** - Look for: "phone number", "contact number", "best number"
   → Action: Select cell phone option from dropdown
   → Success: Phone option selected, dropdown closed

4. **Rate Setting Stage** - Look for: "project rate", "hourly rate", "set your rate"
   → Action: Confirm $500/hour rate setting
   → Success: Rate confirmed, "set project rate" clicked

5. **Terms Acknowledgment Stage** - Look for: "terms and conditions", "acknowledge", "i confirm"
   → Action: Check acknowledgment checkbox, then click Apply button
   → Success: Checkbox checked, apply button enabled

6. **Availability Stage** - Look for: "availability", "add availability", "schedule"
   → Action: Click "Add Availability", select slots, Save, then "Proceed with selection"
   → Success: Slots selected, availability saved, proceed clicked

7. **Final Submit Stage** - Look for: "apply for this project", "submit application", "confirm & submit"
   → Action: Click final submit button
   → Success: Application submitting, loading indicator visible

8. **COMPLETION Stage** - Look for: "thanks, you're all set", "application received"
   → Action: TERMINATE SUCCESSFULLY - task is complete!
   → Success: Success message visible, task finished

**INTELLIGENT TERMINATION CRITERIA:**
✅ STOP when you see: "Thanks, you're all set!" or "Application received"
✅ STOP when you see: "You have already declined" or "Already applied"
✅ STOP when you see: "Project is no longer available" or "Expired"
❌ NEVER stop just because a step takes multiple attempts
❌ NEVER stop without completing availability scheduling

**DECISION-MAKING PRINCIPLES:**
- Analyze each screenshot to identify current workflow stage
- Take the appropriate action for that stage
- Verify success indicators before moving to next stage
- Only terminate when you see definitive completion or blocking messages
- If unsure about current stage, describe what you see and take best action

"""
    
    if login_username and login_password:
        prompt += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
    
    prompt += """Fill out the application form with the following information:
"""
    
    # Add form field data
    if "text_content" in form_data and len(form_data) == 1:
        prompt += form_data["text_content"] + "\n"
    else:
        for field, value in form_data.items():
            if field != "text_content":
                prompt += f"- {field}: {value}\n"
    
    prompt += """
After filling all fields and completing ALL steps (including availability scheduling),
verify you see the success message "Thanks, you're all set!"
"""
    
    return prompt


# =============================================================================
# GLG PLATFORM CLASS
# =============================================================================

class GLGPlatform(BasePlatform):
    """GLG (Gerson Lehrman Group) platform implementation."""

    def __init__(self) -> None:
        super().__init__("GLG")

    def get_platform_config(self) -> Dict[str, Any]:
        """Get GLG-specific configuration for browser automation."""
        return get_glg_platform_config()

    async def prepare_application(self, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured application template for the agent.

        The ConsultPipelineAgent uses this plus cp_writing_style.md to draft
        actual text, then enters it via Computer Use.
        """
        profile_context = consultation_data.get("profile_context", {})

        return {
            "fields": {
                "introduction": {
                    "type": "textarea",
                    "purpose": "Briefly introduce my relevant background for this GLG project.",
                },
                "approach": {
                    "type": "textarea",
                    "purpose": "Explain how I would approach solving the client's problem.",
                },
                "availability": {
                    "type": "textarea",
                    "purpose": "Describe my availability and any timing constraints.",
                },
            },
            "glg_specific": {
                "product_familiarity_strategy": GLG_PRODUCT_FAMILIARITY_STRATEGY,
                "workflow_stages": GLG_WORKFLOW_STAGES,
                "success_indicators": GLG_SUCCESS_INDICATORS,
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
        """Build GLG-specific task prompt for browser automation."""
        return build_glg_task_prompt(
            form_data=form_data,
            login_username=login_username,
            login_password=login_password,
            decline=decline
        )
