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
# GLG-SPECIFIC WORKFLOW STAGES
# =============================================================================

GLG_WORKFLOW_STAGES = {
    "product_familiarity": ["familiarity", "experience with", "which products", "your familiarity"],
    "additional_info": ["additional comments", "tell us more", "provide details", "anything else"],
    "phone_selection": ["phone number", "contact number", "best number", "reach you"],
    "rate_setting": ["project rate", "hourly rate", "set your rate", "rate for this"],
    "terms_acknowledgment": ["terms and conditions", "acknowledge", "i confirm", "bound by"],
    "final_submit": ["apply for this project", "submit application", "confirm & submit"],
    "availability": ["availability", "add availability", "schedule", "when are you available"],
    "completion": ["thanks, you're all set", "all set", "you're all set"],
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


def get_glg_platform_config() -> Dict[str, Any]:
    """
    Get the platform configuration for GLG.
    
    This configuration is passed to BrowserAutomation to enable
    GLG-specific behavior without hardcoding it in the core module.
    
    Returns:
        Platform configuration dict for BrowserAutomation
    """
    return {
        "success_indicators": GLG_SUCCESS_INDICATORS,
        "failure_indicators": GLG_FAILURE_INDICATORS,
        "blocked_indicators": GLG_BLOCKED_INDICATORS,
        "workflow_stages": GLG_WORKFLOW_STAGES,
        "dialog_handler": dismiss_all_glg_dialogs,
        "cookie_selectors": GLG_COOKIE_SELECTORS,
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
        prompt += """Then find and click the DECLINE button to decline this consultation.
Confirm the decline action if prompted.
"""
        return prompt
    
    # Accept workflow
    prompt = """Complete the GLG consultation application form.

**CRITICAL - GLG MULTI-STEP WORKFLOW:**
GLG applications have multiple steps. You MUST complete ALL steps:

1. **Product Familiarity Questions** (if present):
   - For Google/GCP products: Select "4 - My company is offering to customers"
   - For Amazon/AWS/Microsoft products: Select "3 - Evaluated, not offering"
   - For other products: Select "2 - Aware, not evaluated"
   - Check the biography confirmation checkbox

2. **Additional Comments** (textarea):
   - Fill with professional background summary

3. **Phone Selection** (if present):
   - Select the Cell phone option

4. **Rate Setting** (if present):
   - The rate should be $500/hour (usually pre-set)
   - Click "Set project rate" to confirm

5. **Terms & Conditions**:
   - Check the acknowledgment checkbox
   - Click "Apply for this Project"

6. **Availability Scheduling** (CRITICAL - do NOT skip):
   - Click "Add Availability"
   - Select available time slots
   - Click "Save" then "Next"
   - Click "Proceed with selection"

7. **Completion**:
   - Verify you see "Thanks, you're all set!"

**NEVER WAIT FOR HUMAN INPUT** - complete ALL steps automatically.

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
