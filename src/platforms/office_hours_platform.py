"""Office Hours platform implementation.

This module contains ALL Office Hours-specific code:
- Dialog handling (cookie consent, popups)
- Success/failure/blocked indicators
- Survey workflow stages
- Task prompt generation for browser automation

Key difference from other platforms:
- Uses Google OAuth for login (persistent browser session)
- Survey-only platform (no multi-step vetting forms)
- No username/password credentials needed
"""

import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from playwright.async_api import Page

from .base import BasePlatform
from src.browser.cookie_detection import dismiss_dialog_by_selectors


# =============================================================================
# OFFICE HOURS SUCCESS/FAILURE/BLOCKED INDICATORS
# =============================================================================

OFFICE_HOURS_SUCCESS_INDICATORS = [
    # Survey completion messages
    "thank you for completing",
    "survey submitted",
    "response recorded",
    "submission successful",
    "thank you for your response",
    "your response has been recorded",
    "survey complete",
    "thanks for completing",
    "successfully submitted",
]

OFFICE_HOURS_FAILURE_INDICATORS = [
    # Error messages
    "error submitting",
    "something went wrong",
    "try again",
    "unable to submit",
    "submission failed",
    "an error occurred",
    "please try again",
]

OFFICE_HOURS_BLOCKED_INDICATORS = [
    # Survey unavailable states
    "survey closed",
    "already completed",
    "expired",
    "no longer available",
    "survey is closed",
    "already responded",
    "not eligible",
]


# =============================================================================
# OFFICE HOURS WORKFLOW STAGES
# =============================================================================

OFFICE_HOURS_WORKFLOW_STAGES = {
    # Survey workflow stages
    "survey_intro": ["welcome", "survey details", "get started", "begin survey"],
    "questions": ["question", "select", "rate", "choose", "how would you"],
    "completion": ["thank you", "submitted", "complete", "recorded"],
}


# =============================================================================
# OFFICE HOURS DIALOG SELECTORS
# =============================================================================

# Cookie consent banner (Office Hours may use various providers)
OFFICE_HOURS_COOKIE_DIALOG = {
    "dialog_selectors": [
        '[class*="cookie"]',
        '[id*="cookie"]',
        '[class*="consent"]',
        '.cookie-banner',
        '#cookie-banner',
        '[class*="gdpr"]',
    ],
    "dismiss_selectors": [
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("OK")',
        'button:has-text("I Agree")',
        'button:has-text("Got it")',
        'button:has-text("Close")',
        '[class*="accept"]',
    ],
    "description": "Office Hours cookie consent banner"
}

# Additional cookie button selectors (for core cookie detection)
OFFICE_HOURS_COOKIE_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("OK")',
    'button:has-text("I Agree")',
]


# =============================================================================
# OFFICE HOURS DIALOG HANDLER
# =============================================================================

async def dismiss_office_hours_cookie_banner(page: Page) -> bool:
    """
    Dismiss Office Hours cookie consent banner.

    Args:
        page: Playwright page object

    Returns:
        True if banner was found and dismissed, False otherwise
    """
    return await dismiss_dialog_by_selectors(
        page,
        dialog_selectors=OFFICE_HOURS_COOKIE_DIALOG["dialog_selectors"],
        dismiss_selectors=OFFICE_HOURS_COOKIE_DIALOG["dismiss_selectors"],
        description=OFFICE_HOURS_COOKIE_DIALOG["description"]
    )


async def dismiss_all_office_hours_dialogs(page: Page, max_iterations: int = 3) -> Dict[str, Any]:
    """
    Dismiss all known Office Hours-specific dialogs in sequence.

    This is the main entry point for Office Hours dialog handling. It handles:
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
            if await dismiss_office_hours_cookie_banner(page):
                results["cookie_banner"] = True
                dismissed_any = True
                await asyncio.sleep(0.3)

        # If nothing was dismissed, we're done
        if not dismissed_any:
            break

        logger.debug(f"Office Hours dialog dismissal iteration {iteration + 1}: {results}")

    return results


def get_office_hours_platform_config() -> Dict[str, Any]:
    """
    Get the platform configuration for Office Hours.

    This configuration is passed to BrowserAutomation to enable
    Office Hours-specific behavior without hardcoding it in the core module.

    Returns:
        Platform configuration dict for BrowserAutomation
    """
    return {
        "success_indicators": OFFICE_HOURS_SUCCESS_INDICATORS,
        "failure_indicators": OFFICE_HOURS_FAILURE_INDICATORS,
        "blocked_indicators": OFFICE_HOURS_BLOCKED_INDICATORS,
        "workflow_stages": OFFICE_HOURS_WORKFLOW_STAGES,
        "dialog_handler": dismiss_all_office_hours_dialogs,
        "cookie_selectors": OFFICE_HOURS_COOKIE_SELECTORS,
        # Key difference: Google OAuth login (no username/password needed)
        "auth_type": "google_oauth",
        "uses_browser_profile": True,
    }


# =============================================================================
# OFFICE HOURS TASK PROMPT GENERATION
# =============================================================================

def build_office_hours_task_prompt(
    form_data: Dict[str, Any],
    login_username: Optional[str] = None,
    login_password: Optional[str] = None,
    decline: bool = False
) -> str:
    """
    Build an Office Hours-specific task prompt for browser automation.

    This generates detailed instructions for the AI to complete
    Office Hours paid surveys.

    Key difference from other platforms:
    - No login credentials needed (uses persistent Google session)
    - Survey questions instead of vetting forms
    - Single-page or multi-page survey completion

    Args:
        form_data: Form field data to fill
        login_username: Ignored - Office Hours uses Google OAuth
        login_password: Ignored - Office Hours uses Google OAuth
        decline: Whether to decline instead of complete

    Returns:
        Complete task prompt string
    """
    if decline:
        return """DECLINE the Office Hours survey opportunity.

Navigate to the survey and close or exit without completing.
If there is a "Skip" or "Exit Survey" option, use that.
"""

    # Complete survey workflow
    prompt = """Complete the Office Hours paid survey.

**CRITICAL - GOOGLE OAUTH LOGIN:**
Office Hours uses Google authentication (NOT username/password). To login:
1. Look for "Sign in with Google", "Continue with Google", or "Log in with Google" button
2. Click it to authenticate with your Google account (kelapure@gmail.com)
3. If a Google account picker appears, select the correct account
4. If already logged in via Google, you may be redirected automatically
5. DO NOT look for username/password fields - Office Hours only uses Google OAuth

**SURVEY COMPLETION WORKFLOW:**
1. **Navigate to Dashboard**:
   - After login, go to the surveys/home page
   - Look for available paid surveys to complete

2. **Complete Survey Questions**:
   - Answer ALL questions thoughtfully
   - Use CP writing style for free-text responses: direct, confident, data-driven
   - For multiple choice: select the most accurate option based on your experience
   - For rating scales: provide honest assessments
   - For text fields: provide concise but substantive responses

3. **Submit Survey**:
   - Click "Submit" or "Complete Survey"
   - Verify you see a confirmation message ("Thank you", "Survey complete", etc.)

**NEVER WAIT FOR HUMAN INPUT** - complete ALL steps automatically.

"""

    # Add any survey context from form_data
    if form_data:
        prompt += """Survey context and guidance:
"""
        if "text_content" in form_data and len(form_data) == 1:
            prompt += form_data["text_content"] + "\n"
        else:
            for field, value in form_data.items():
                if field != "text_content":
                    prompt += f"- {field}: {value}\n"

    prompt += """
After completing the survey, verify you see a "Thank you" or confirmation message.
"""

    return prompt


# =============================================================================
# OFFICE HOURS PLATFORM CLASS
# =============================================================================

class OfficeHoursPlatform(BasePlatform):
    """Office Hours platform implementation.

    Key characteristics:
    - Survey-only platform ($50 for 15-minute surveys)
    - Uses Google OAuth for authentication (persistent browser session)
    - No username/password credentials needed
    """

    def __init__(self) -> None:
        super().__init__("OfficeHours")

    def get_platform_config(self) -> Dict[str, Any]:
        """Get Office Hours-specific configuration for browser automation."""
        return get_office_hours_platform_config()

    async def prepare_application(self, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return a structured survey template for the agent.

        The ConsultPipelineAgent uses this plus cp_writing_style.md to draft
        actual text, then enters it via Computer Use.
        """
        profile_context = consultation_data.get("profile_context", {})

        return {
            "fields": {
                "survey_responses": {
                    "type": "mixed",
                    "purpose": "Answer survey questions - may include multiple choice, ratings, and free text",
                },
            },
            "office_hours_specific": {
                "workflow_stages": OFFICE_HOURS_WORKFLOW_STAGES,
                "success_indicators": OFFICE_HOURS_SUCCESS_INDICATORS,
                "login_type": "google_oauth",
                "uses_browser_profile": True,
            },
            "context": {
                "project_description": consultation_data.get("project_description", ""),
                "survey_topic": consultation_data.get("survey_topic", ""),
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
        """Build Office Hours-specific task prompt for browser automation.

        Note: login_username and login_password are ignored since Office Hours
        uses Google OAuth with persistent browser session.
        """
        return build_office_hours_task_prompt(
            form_data=form_data,
            login_username=login_username,
            login_password=login_password,
            decline=decline
        )
