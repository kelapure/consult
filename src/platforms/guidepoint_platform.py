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

