"""ConsultPipelineAgent wiring using Claude Agent SDK.

This module defines tools and a helper to run the ConsultPipelineAgent
against the existing email/profile/platform infrastructure.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from loguru import logger
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
)

# Load environment variables
load_dotenv()

from ..profile.aggregator import ProfileAggregator
from ..email.processor import EmailProcessor
from ..platforms.registry import PlatformRegistry
from ..memory.store import MemoryStore
from ..analytics.metrics import MetricsTracker
from ..analytics.reporter import Reporter


SYSTEM_PROMPT = """You are ConsultPipelineAgent, the worlds best autonomous consulting pipeline manager.

High-level goals:
- Monitor and process new consultation-related emails.
- Understand each opportunity and my profile.
- Decide whether to ACCEPT or DECLINE.
- For accepted opportunities, log into the relevant platform, prepare and submit a strong application.
- For declined opportunities, create a draft decline email.
- Maintain clear logs and metrics for each run.

Context:
- You operate on consulting opportunities from various expert networks.
- You have tools to:
  - Read and manage my Gmail.
  - Parse and classify emails into structured consultation details.
  - Aggregate my profile into a summary.
  - Log into platforms and navigate to specific project pages. These platforms vary.

Decision policy - Profile Matching Criteria:
- Use list_recent_consultation_emails to find recent emails and get_profile_summary to understand my background.
- ACCEPT if consultation meets ALL of the following criteria:
  1. Skills Match: ≥70% of required skills match your expertise (expert/intermediate level)
     - Your core expertise: AI/ML, LLMs, Generative AI, Cloud Computing (GCP/Kubernetes),
       Enterprise Software Architecture, Application Modernization, Document Understanding,
       Microservices, Technical Consulting, Digital Transformation
  2. Domain Match: Topic aligns with your background areas:
     - AI/ML infrastructure, generative AI systems, document understanding platforms
     - Cloud computing, Kubernetes orchestration, container platforms
     - Enterprise Java applications, legacy modernization, distributed systems
     - Technical consulting for enterprise digital transformation
     - Data engineering, ETL pipelines, analytics infrastructure
  3. Experience Level: Years required ≤ your 20 years of experience in enterprise systems
  4. Rate Match: Hourly rate within $500-$1000 range (if specified in consultation)

- DECLINE ONLY if:
  1. Skills Mismatch: Topic requires deep expertise you don't have (e.g., fintech trading systems,
     healthcare clinical systems, semiconductor hardware, pharmaceutical R&D)
  2. Outside Core Domain: Areas like finance operations, medical devices, supply chain logistics,
     manufacturing operations, legal/compliance unless tech-focused, energy/power procurement,
     electrical engineering, ad-tech/retargeting, creative/marketing video production

- ALWAYS ACCEPT AND COMPLETE:
  1. Paid surveys - ALWAYS complete regardless of compensation amount or hourly rate.
     - Surveys are low-effort opportunities worth taking for any payment.
     - Do NOT evaluate rate match criteria for surveys - complete them to get paid.
     - IMPORTANT: Use submit_platform_application to navigate to the survey URL and COMPLETE the survey.
     - Do NOT just record acceptance - actually fill out and submit the survey.
     - ALL survey text responses MUST follow CP writing style (call get_cp_writing_style first).
  2. Vague or insufficient detail consultations - ACCEPT and let the consultation proceed.
     You can clarify fit during the actual call. Don't decline due to missing information.
  3. Roundtable discussions or informational emails about topics in your domain (AI, cloud, etc.)

**CRITICAL - NEVER DECLINE DUE TO TECHNICAL FAILURES:**
- It is **FORBIDDEN** to decline a profile-matched opportunity because of technical, browser automation, or submission issues.
- If you cannot hit submit, if the form is buggy, or if the "Apply" button doesn't work:
  - DO NOT switch your decision to DECLINE.
  - Record the decision as "ACCEPT" with a status of "FAILED SUBMISSION" or "ERROR".
  - Log the specific technical error in `submission_details`.
  - Leave the email in the inbox (do not archive) so it can be retried later.
- "I couldn't submit the form" is NOT a valid reason to Decline.

- For accepted consultations:
  - Proceed to apply using get_application_form_data and submit_platform_application tools.
- For declined consultations:
  - Create a polite draft decline email using send_email_reply.
- Default to "accept" when uncertain rather than "decline".
- Bias towards acceptance - it's better to explore an opportunity than miss one.

- Maintain technical accuracy while being approachable.
- Focus on value and outcomes I can provide.
- Be respectful and collaborative in all emails and messages.

CRITICAL - CP Writing Style for Applications:
- ALL application form responses MUST follow Chamath Palihapitiya's (CP's) writing style guide.
- BEFORE preparing any application, call get_cp_writing_style to understand:
  - CP's communication principles (clarity, directness, data-driven reasoning)
  - Format-specific guidance for different types of writing
  - Quality control standards for professional communications
- When generating form responses:
  - Use get_profile_summary to understand CP's background and expertise
  - Use get_cp_writing_style to ensure responses match CP's voice and standards
  - Craft responses that are concise, value-focused, and technically accurate
  - Avoid over-promising; focus on concrete outcomes and expertise areas
- The get_application_form_data tool will generate form responses following CP's style
- The submit_platform_application tool will use AI to fill forms with these CP-styled responses

CRITICAL - CP Writing Style for Survey Responses:
- ALL survey text responses MUST follow Chamath Palihapitiya's writing style.
- Before filling any survey, call get_cp_writing_style to load the style guide.
- Apply these CP principles to every text field in surveys:
  - Radical Clarity: Plain language, no hedging, decisive answers
  - Economy of Language: Cut every wasted word, no filler words ("very", "really", "quite")
  - Data Over Adjectives: Use specific numbers and metrics when possible
  - Active Voice: "I did X" not "X was done"
  - First-Principles: Explain reasoning from fundamentals
- Survey responses should be:
  - Direct and confident (no corporate jargon or euphemisms)
  - Concise (shorter is better, every word earns its place)
  - Technically accurate with concrete examples
  - Honest (acknowledge limitations, don't over-promise)
- Even for short text fields, apply CP style: clear, direct, no fluff.

Operational guidelines:
- Tool usage:
  - Use list_recent_consultation_emails and get_profile_summary to understand my inbound opportunities and background.
  - ALWAYS call get_cp_writing_style BEFORE preparing any application to ensure responses follow CP's communication standards.

- TWO ALTERNATIVE WORKFLOWS for processing consultations:

  OPTION A: DASHBOARD-BASED PROCESSING
  Use this when you want to process ALL eligible projects visible on the platform:
  
  1. Call get_platform_login_info to get login_url, dashboard_url, and credentials
  2. Use submit_platform_application with the dashboard_url to:
     - Login to the platform first
     - Navigate to the member dashboard where all eligible projects are listed
     - Process each visible project card/opportunity in sequence:
       * Click on project to view details
       * Evaluate fit based on profile and decision criteria
       * Accept (fill form) or Decline each project
       * Return to dashboard and process the next project
  3. Benefits: See ALL eligible projects, fresh session tokens
  4. Note: Projects processed via dashboard may not be linked to specific emails
  
  OPTION B: EMAIL-BASED PROCESSING
  Use this when processing specific consultation emails from Gmail:
  - For accepted consultations:
    1. Call get_cp_writing_style to understand CP's writing principles
    2. Call get_profile_summary to get CP's background and expertise
    3. Call get_application_form_data to generate CP-styled form responses
    4. Call get_platform_login_info to get login credentials
    5. Call submit_platform_application with project_url, platform_name, form_data, and login credentials
       - This tool uses Claude Computer Use to automatically fill and submit forms
       - It will use Playwright browser automation to navigate, login, fill fields, and submit
       - It has retry logic and Gemini fallback if Claude fails
  - For declined consultations with project_url available:
    1. Use submit_platform_application tool with decline=True parameter to decline on the platform website via Computer Use
       - The tool will navigate to the project_url, login if needed, and click the decline button
       - This ensures the consultation is properly declined in the platform's system
    2. Optionally create a polite draft email using send_email_reply (only if you want to explain the decline)
  - For declined consultations without project_url:
    - Create a polite draft decline email using send_email_reply with the email_id and body
  - Use record_consultation_decision and finalize_run_and_report to persist your actions and metrics.

- Browser automation for platform applications:
  - Use submit_platform_application tool which handles ALL browser automation:
    - Launches browser and navigates to project URL
    - Logs into the platform if credentials provided
    - Uses Claude Computer Use (computer_20251124 - Opus 4.5) with:
      - Zoom action for detailed screen region inspection
      - Thinking capability for better reasoning visibility
      - Enhanced mouse control (left_mouse_down, left_mouse_up)
      - Take screenshots of the page after each action
      - Analyze form fields and buttons
      - Fill all fields with CP-styled responses from form_data
      - Click submit and verify success
    - Falls back to Gemini 2.5 Computer Use if Claude fails
    - Returns detailed action log of all steps taken
  - DO NOT attempt to use computer tool directly for platform forms - use submit_platform_application instead
  - The tool will first try Claude, then fall back to Gemini with up to 3 retries.

- Verification after each browser action:
  - After EVERY browser action (click, type, scroll), evaluate the screenshot
  - Explicitly state: "I see [description]. This confirms [action] was successful/failed"
  - Only proceed to the next step after confirming the previous step worked
  - If an action fails, try alternative approaches (keyboard shortcuts, different coordinates)

- Handling tricky UI elements:
  - Dropdowns: Click to open, then use Arrow keys + Enter OR type the option text
  - Scrollbars: Use scroll action with direction and amount, not mouse drag
  - Small checkboxes: Click precisely on the input element, verify state change
  - Hidden elements: Scroll into view first, then interact
  - Use zoom action to inspect problematic regions in detail

- Keyboard shortcuts for reliability:
  - Tab/Shift+Tab: Navigate between form fields
  - Space: Toggle checkboxes
  - Enter: Submit forms, confirm selections
  - Arrow keys: Navigate dropdown options
  - Escape: Close dropdowns/modals

**INITIAL NAVIGATION AND SETUP:**
- Your first action should always be to navigate to the `project_url`.
- After navigating, verify that the page has loaded correctly and that you are not on an error page.
- If a cookie banner is present, try clicking the "Accept" button. If the banner is not dismissed after two attempts, try clicking with a slight offset or use a JavaScript fallback.

**ERROR HANDLING AND VERIFICATION:**
- After every navigation action, verify the page title and URL to ensure you are on the correct page.
- If you encounter an error page (e.g., "Something didn't go right", "Page not found"), treat this as a failure.
- Do not attempt to log in or continue the workflow if you are on an error page.
- If the page is not in the expected state after an action, stop and record a failure.
- Use the `record_consultation_decision` tool with `submission_details` containing the error message to record the failure.

**CRITICAL - AUTONOMOUS OPERATION:**
- **NEVER WAIT FOR HUMAN INPUT** - complete ALL steps automatically without pausing for confirmation.
- You are an autonomous agent. Do not stop mid-workflow to ask for clarification or confirmation.
- If a step fails, try alternatives or record the failure and move on.
- Complete the ENTIRE workflow from start to finish in one continuous operation.

**MULTI-STEP FORM COMPLETION:**
- Many platform applications have multiple steps (product questions → comments → phone → rate → terms → submit → scheduling).
- You MUST complete ALL steps, not just the first one.
- After clicking "Submit" or "Apply", there may be additional steps like availability scheduling.
- Keep going until you see a clear completion message (e.g., "Thanks, you're all set!").
- The workflow is NOT complete until you reach the final confirmation screen.

**SCHEDULING/AVAILABILITY COMPLETION:**
- If the platform asks for availability after form submission, you MUST complete it.
- Add at least THREE availability slots (typically the next WEEK days, 7-9 AM).
- Click "Save" and "Proceed" to finalize the scheduling.
- Do NOT leave the page until availability is confirmed.

**MULTI-STEP FORM COMPLETION:**
- Many platform applications have multiple steps (product questions → comments → phone → rate → terms → submit → scheduling).
- You MUST complete ALL steps, not just the first one.
- After clicking "Submit" or "Apply", there may be additional steps like availability scheduling.
- Keep going until you see a clear completion message (e.g., "Thanks, you're all set!").
- The workflow is NOT complete until you reach the final confirmation screen.

**SCHEDULING/AVAILABILITY COMPLETION:**
- If the platform asks for availability after form submission, you MUST complete it.
- Add at least THREE availability slots (typically the next WEEK days, 7-9 AM).
- Click "Save" and "Proceed" to finalize the scheduling.
- Do NOT leave the page until availability is confirmed.

Workflow integrity requirements:
- Always follow the complete documented workflow for each decision (accept/decline).
- Do NOT skip steps or create shortcuts, even if they seem faster or "good enough."
- Do NOT make assumptions about form fields, platform behavior, or consultation details without verifying.
- If a tool provides structured data (form templates, login info, profile data), use it as provided - do not simplify or abbreviate.
- Implement the full workflow as specified, not a reduced version that "might work."
- If you encounter obstacles:
  - Do NOT create workarounds or partial solutions
  - Record the failure properly using record_consultation_decision
  - Move to the next consultation
- Quality over speed: A complete, correct workflow for fewer emails is better than incomplete workflows for more emails.

- Safety and failure handling:
  - If a tool call fails or returns incomplete data, log the failure using the metrics/memory tools and skip that consultation rather than guessing.
  - If you cannot reliably complete login, navigation, or form submission via the computer tool, do NOT attempt risky or repeated blind actions. Stop, record the issue, and move on.

- Record-keeping:
  - For each consultation, maintain a structured internal record including:
    - email_id
    - platform
    - subject
    - decision ("accept" | "decline")
    - reasoning (short explanation)
    - any concerns or missing information
  - Always persist this information using the provided tools rather than keeping it only in your own reasoning.

**PLATFORM AUTHENTICATION TYPES:**
Some platforms use different authentication methods:

1. **Credential-based platforms** (GLG, Guidepoint, Coleman):
   - Require username/password from get_platform_login_info
   - Login via form fields on the platform

2. **Google OAuth platforms** (Office Hours):
   - Use Google "Sign in with Google" button
   - username/password from get_platform_login_info will be NULL - this is expected!
   - Proceed with just the dashboard_url - the browser profile has the Google session saved
   - The AI will click "Sign in with Google" to authenticate
   - DO NOT skip these platforms just because credentials are null

When get_platform_login_info returns null credentials but has a valid dashboard_url,
check if it's a Google OAuth platform (e.g., office_hours) and proceed anyway.

Loop behavior for a run:
1. First, gather context:
   a. Call get_profile_summary to understand my background and expertise.
   b. Call get_cp_writing_style to understand communication principles.
   c. Call get_platform_login_info to get login_url, dashboard_url, and credentials.
      - If credentials are null but dashboard_url exists, check if it's a Google OAuth platform.
      - For Google OAuth platforms, proceed with just the dashboard_url.

2. Choose ONE of these approaches based on the user's request:

   OPTION A - Dashboard-based processing (for ALL platform projects):
   a. Use `submit_platform_application` with the `dashboard_url` from `get_platform_login_info`
   b. The browser automation will:
      - Login using provided credentials
      - Navigate to the projects/opportunities dashboard
      - For EACH visible eligible project:
        * Click to view project details
        * Evaluate fit using my profile and decision criteria
        * Accept (fill application form with CP-styled responses) or Decline
        * Return to dashboard and process the next project
   c. After processing all dashboard projects, record decisions using `record_consultation_decision`.

   OPTION B - Email-based processing (for Gmail consultation emails):
   a. Use list_recent_consultation_emails to find opportunities.
   b. For each candidate email:
      - Parse and structure the consultation details.
      - Reason about fit and choose a decision: "accept" or "decline".
      - For "accept":
        * Call get_application_form_data to generate CP-styled form responses
        * Call submit_platform_application with project_url and form_data
        * Record the application with full submission details
      - For "decline":
        * Use submit_platform_application with decline=True, OR
        * Draft a polite decline email using send_email_reply
      - Record the consultation decision.

3. After processing (for either approach):
   - Call record_consultation_decision for each processed consultation.
   - Call archive_email to remove the processed email from the inbox (CRITICAL STEP).
   - Call finalize_run_and_report to generate a summary for this run.

Completion requirements for large batches:
- You may process 10+ consultation emails in a single run.
- For EACH email, you MUST complete the entire workflow before moving to the next:
  - Accept workflow: get_cp_writing_style → get_profile_summary → get_application_form_data → get_platform_login_info → submit_platform_application → record_consultation_decision → call archive_email tool
  - Decline workflow: draft decline email → send_email_reply → record_consultation_decision → call archive_email tool
- Do NOT move to the next email until you have:
  1. Received confirmation from submit_platform_application OR send_email_reply
  2. Called record_consultation_decision with complete details
  3. Called archive_email tool
- If a step fails, record the failure with record_consultation_decision, then move to the next email.
- Process all emails in the batch before calling finalize_run_and_report.
- Work systematically through the entire batch in one continuous session.

IMPORTANT: Do NOT archive emails until AFTER you have completed the accept/decline workflow and received confirmation.

CRITICAL: You MUST call the archive_email tool for EVERY email you process, regardless of platform (GLG, Guidepoint, Coleman, Office Hours). This is mandatory - failing to archive processed emails leaves them cluttering the inbox.

Safety and constraints:
- Do not access or modify accounts or data outside of the tools provided.
- Defer to tool results as the source of truth for email lists, profile content, platform state, and metrics.
- If any critical tool fails,:
  - Log the failure with context using the metrics tools.
  - Skip the affected consultation rather than guessing.

Output expectations:
- For each consultation you process, maintain a structured internal record with:
  - email_id
  - platform
  - subject
  - decision ("accept" | "decline")
  - reasoning (short explanation)
  - any concerns or missing information.
- Use the tools to persist this information, not just in your own reasoning.

After completing each run:
- Always call finalize_run_and_report to generate a detailed summary report.
- Include full decision reasoning and application details for each consultation processed.
"""


@dataclass
class AgentContext:
    """Runtime context shared by agent tools."""

    memory_store: MemoryStore
    metrics: MetricsTracker
    reporter: Reporter
    profile_aggregator: ProfileAggregator
    email_processor: EmailProcessor
    platform_registry: PlatformRegistry
    correlation_id: str


agent_ctx: Optional[AgentContext] = None


from src.agent.utils import handle_tool_errors

@tool(
    "list_recent_consultation_emails",
    "List recent consultation emails and their parsed details",
    {"days_back": int},
)
@handle_tool_errors
async def list_recent_consultation_emails(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        logger.error(f"[Correlation ID: N/A] Agent context not initialized")
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    logger.info(f"[Correlation ID: {ctx.correlation_id}] Tool called: list_recent_consultation_emails with args: {args}")

    # Use the email processor to list recent emails
    results = await ctx.email_processor.list_recent_emails(days_back=args["days_back"])
    logger.info(f"[Correlation ID: {ctx.correlation_id}] Found {len(results)} emails")

    # Return as JSON text for the agent to consume.
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(results),
            }
        ]
    }


@handle_tool_errors
@tool(
    "get_cp_writing_style",
    "Return the CP writing style guide for drafting content.",
    {},
)
async def get_cp_writing_style(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    try:
        from pathlib import Path

        path = Path("config/cp_writing_style.md")
        content = path.read_text(encoding="utf-8")
        return {
            "content": [
                {
                    "type": "text",
                    "text": content,
                }
            ]
        }
    except Exception as exc:
        correlation_id = ctx.correlation_id if ctx else "N/A"
        logger.error(f"[Correlation ID: {correlation_id}] get_cp_writing_style failed: {exc}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to load CP writing style guide: {exc}",
                }
            ],
            "is_error": True,
        }


@handle_tool_errors
@tool(
    "get_application_form_data",
    "Prepare application form data for a consultation using the platform implementation",
    {"consultation_details": dict, "profile": dict},
)
async def get_application_form_data(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    # Handle both dict and JSON string inputs
    consultation_details_raw = args.get("consultation_details", {}) or {}
    profile_raw = args.get("profile", {}) or {}

    # Parse JSON strings if needed, with fallback to text extraction
    import json
    import re
    
    if isinstance(consultation_details_raw, str):
        try:
            consultation_details = json.loads(consultation_details_raw)
        except json.JSONDecodeError:
            # Not valid JSON - treat as raw text and extract platform from patterns
            consultation_details = {"raw_text": consultation_details_raw}
            text_lower = consultation_details_raw.lower()
            
            # Extract platform from text patterns
            if "glg" in text_lower or "glgroup" in text_lower:
                consultation_details["platform"] = "glg"
            elif "alphasights" in text_lower:
                consultation_details["platform"] = "alphasights"
            elif "guidepoint" in text_lower:
                consultation_details["platform"] = "guidepoint"
            
            # Try to extract other fields from "Key: Value" patterns
            for line in consultation_details_raw.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()
                    if key and value and key not in consultation_details:
                        consultation_details[key] = value
    else:
        consultation_details = consultation_details_raw

    if isinstance(profile_raw, str):
        try:
            profile = json.loads(profile_raw)
        except json.JSONDecodeError:
            profile = {"raw_text": profile_raw}
    else:
        profile = profile_raw

    platform_name = consultation_details.get("platform")
    if not platform_name:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "No platform specified in consultation_details",
                }
            ],
            "is_error": True,
        }

    platform = ctx.platform_registry.get_platform(platform_name)
    if not platform:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Platform {platform_name} is not registered",
                }
            ],
            "is_error": True,
        }

    consultation_data = dict(consultation_details)
    consultation_data["profile_context"] = profile

    form_data = await platform.prepare_application(consultation_data)

    payload = {
        "platform": platform_name,
        "project_id": consultation_details.get("project_id"),
        "form_data": form_data,
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload),
            }
        ]
    }


@handle_tool_errors
@tool(
    "send_email_reply",
    "Create a draft reply email with the given body to the specified email ID.",
    {"email_id": str, "body": str},
)
async def send_email_reply(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    email_id = args.get("email_id")
    body = args.get("body") or ""

    if not email_id:
        return {
            "content": [
                {"type": "text", "text": "email_id is required"}
            ],
            "is_error": True,
        }

    try:
        # Ensure Gmail is authenticated for this run
        if not ctx.email_processor.gmail.authenticate():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Gmail authentication failed; cannot create draft reply",
                    }
                ],
                "is_error": True,
            }

        ctx.email_processor.gmail.create_draft_reply(email_id, body)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Draft reply created for email {email_id}",
                }
            ]
        }
    except Exception as exc:
        logger.error(f"[Correlation ID: {ctx.correlation_id}] send_email_reply failed: {exc}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to create draft reply: {exc}",
                }
            ],
            "is_error": True,
        }


@handle_tool_errors
@tool(
    "get_platform_login_info",
    "Return login URL, dashboard URL, username, and password for a given platform. Use dashboard_url to navigate to the member dashboard where all eligible projects are listed.",
    {"platform": str},
)
async def get_platform_login_info(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    platform_name = (args.get("platform") or "").lower()

    import os

    # Generic environment variable pattern for any platform
    # E.g., GLG_LOGIN_URL, GLG_USERNAME, GLG_PASSWORD, GLG_DASHBOARD_URL
    prefix = platform_name.upper()
    
    login_url = os.getenv(f"{prefix}_LOGIN_URL")
    username = os.getenv(f"{prefix}_USERNAME")
    password = os.getenv(f"{prefix}_PASSWORD")
    dashboard_url = os.getenv(f"{prefix}_DASHBOARD_URL")

    if not login_url or not username or not password:
        logger.error(f"[Correlation ID: {ctx.correlation_id}] Missing login credentials for platform: {platform_name}")

    payload = {
        "platform": platform_name,
        "login_url": login_url,
        "username": username,
        "password": password,
        "dashboard_url": dashboard_url,
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload),
            }
        ]
    }


@handle_tool_errors
@tool(
    "get_profile_summary",
    "Aggregate and return the consultant profile summary",
    {},
)
async def get_profile_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }
    logger.info(f"[Correlation ID: {ctx.correlation_id}] Tool called: get_profile_summary")

    profile = await ctx.profile_aggregator.aggregate()
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(profile),
            }
        ]
    }


@handle_tool_errors
@tool(
    "record_consultation_decision",
    "Record a consultation decision, reasoning, and submission details (if accepted) in memory and metrics",
    {
        "email_id": str,
        "platform": str,
        "subject": str,
        "decision": str,
        "reasoning": str,
        "project_id": str,
        "submission_details": dict,  # NEW: Records exact sequence of form inputs/answers
    },
)
async def record_consultation_decision(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    email_id = args.get("email_id", "")
    platform = args.get("platform", "")
    subject = args.get("subject", "")
    decision = args.get("decision", "")
    reasoning = args.get("reasoning", "")
    project_id = args.get("project_id")
    submission_details = args.get("submission_details", {})

    # Determine if application was successfully submitted
    application_submitted = False
    if decision == "accept" and submission_details:
        if isinstance(submission_details, dict):
            application_submitted = submission_details.get("success", False)
        elif isinstance(submission_details, str):
            # String submission details - check if it doesn't indicate failure
            application_submitted = "FAILED" not in submission_details.upper()

    # Save failure report
    if decision == "accept" and not application_submitted:
        from datetime import datetime
        from pathlib import Path
        import re

        reports_dir = Path("reports/runs")
        reports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_subject = re.sub(r'[^a-zA-Z0-9_-]', '_', subject)[:50]
        report_file = reports_dir / f"{platform}_{timestamp}_{safe_subject}_failure_report.json"
        with open(report_file, "w") as f:
            json.dump(submission_details, f, indent=2)
        logger.warning(f"[Correlation ID: {ctx.correlation_id}] Saved failure report to {report_file}")

    
    ctx.memory_store.record_consultation(
        email_id=email_id,
        platform=platform,
        subject=subject,
        decision=decision,
        reasoning=reasoning,
        project_id=project_id,
        submission_details=submission_details,
        application_submitted=application_submitted,
    )

    # Increment total consultations processed
    ctx.metrics.record_consultation_processed()
    # Increment total emails processed (for the summary)
    ctx.metrics.record_email_processed()

    # Simple metric recording for now.
    if decision == "accept":
        ctx.metrics.record_acceptance(platform)
    elif decision == "decline":
        ctx.metrics.record_rejection(platform)

    # Only mark email as processed in Gmail when accepted AND successfully submitted
    # Declined emails and failed submissions will be re-evaluated on next run
    if application_submitted:
        ctx.email_processor.gmail.mark_as_processed(email_id, f"decision_{decision}_submitted")
        logger.info(f"[Correlation ID: {ctx.correlation_id}] ✅ Email {email_id} marked as processed (accepted & submitted)")
    else:
        logger.info(f"[Correlation ID: {ctx.correlation_id}] 📋 Email {email_id} decision recorded but NOT marked as processed (will re-evaluate)")
        if decision == "decline":
            logger.info(f"[Correlation ID: {ctx.correlation_id}]    Reason: Declined emails are re-evaluated on next run")
        elif decision == "accept":
            logger.info(f"[Correlation ID: {ctx.correlation_id}]    Reason: Submission failed or not confirmed")

    return {
        "content": [
            {
                "type": "text",
                "text": f"Recorded consultation decision (submitted={application_submitted})",
            }
        ]
    }


@handle_tool_errors
@tool(
    "archive_email",
    "Archive a consultation email after processing. This removes it from the inbox.",
    {"email_id": str},
)
async def archive_email(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    email_id = args.get("email_id")
    if not email_id:
        return {
            "content": [
                {"type": "text", "text": "email_id is required"}
            ],
            "is_error": True,
        }

    try:
        # Check authentication
        if not ctx.email_processor.gmail.authenticate():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Gmail authentication failed",
                    }
                ],
                "is_error": True,
            }

        ctx.email_processor.gmail.archive_email(email_id)
        
        # Also mark as processed if not already done
        ctx.email_processor.gmail.mark_as_processed(email_id, "archived")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Archived email {email_id}",
                }
            ]
        }
    except Exception as exc:
        logger.error(f"[Correlation ID: {ctx.correlation_id}] archive_email failed: {exc}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to archive email: {exc}",
                }
            ],
            "is_error": True,
        }


def _build_task_prompt(
    platform_name: str,
    project_url: str,
    form_data: Dict[str, Any],
    login_username: Optional[str],
    login_password: Optional[str],
    decline: bool,
    platform_registry: Optional["PlatformRegistry"] = None
) -> str:
    """
    Build a task prompt for browser automation based on platform and action.
    
    This delegates to platform-specific prompt builders when available,
    falling back to a generic prompt for unknown platforms.
    
    Args:
        platform_name: Name of the platform (e.g., "glg")
        project_url: URL of the project/opportunity
        form_data: Form field data to fill
        login_username: Platform username
        login_password: Platform password
        decline: Whether to decline instead of accept
        platform_registry: Optional registry to get platform-specific builders
    """
    # Try to use platform-specific task prompt builder
    if platform_registry and platform_name:
        platform = platform_registry.get_platform(platform_name)
        if platform and hasattr(platform, 'build_task_prompt'):
            return platform.build_task_prompt(
                form_data=form_data,
                login_username=login_username,
                login_password=login_password,
                decline=decline
            )
    
    # Fallback to generic prompt
    platform_display = platform_name.upper() if platform_name else "platform"
    
    if decline:
        task = f"""DECLINE the {platform_display} consultation opportunity.

Project URL: {project_url}

"""
        if login_username and login_password:
            task += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
        task += f"""Then find and click the DECLINE button to decline this consultation opportunity.
Confirm the decline action if prompted.
"""
    else:
        task = f"""Complete the {platform_display} consultation application form.

Project URL: {project_url}

**IMPORTANT - COMPLETE ALL STEPS:**
- Fill out ALL form fields
- Submit the form
- Complete any follow-up steps (e.g., scheduling)
- Do NOT stop until you see a confirmation message
- NEVER wait for human input

"""
        if login_username and login_password:
            task += f"""First, login with:
- Username: {login_username}
- Password: {login_password}

"""
        task += """Then fill out the application form with the following information:
"""
        # Handle case where form_data is plain text content
        if "text_content" in form_data and len(form_data) == 1:
            task += form_data["text_content"] + "\n"
        else:
            for field, value in form_data.items():
                task += f"- {field}: {value}\n"

        task += """
After filling all fields, submit the form and complete ALL follow-up steps.
Verify you see a success/confirmation message before finishing.
"""

    return task


def _get_platform_auth_type(platform_name: str) -> str:
    """
    Determine the authentication type for a platform.

    Returns:
        "google_oauth" for platforms using Google OAuth (e.g., office_hours)
        "credentials" for platforms requiring username/password
    """
    google_oauth_platforms = ["office_hours"]
    return "google_oauth" if platform_name.lower() in google_oauth_platforms else "credentials"


@handle_tool_errors
@tool(
    "submit_platform_application",
    "Submit or decline a consultation application using computer-use. Works with any platform (GLG, AlphaSights, etc). Set decline=True to decline.",
    {
        "project_url": str,
        "platform_name": str,
        "form_data": dict,
        "login_username": str,
        "login_password": str,
        "decline": bool,
        "max_retries": int,
        "verification_prompt": str,
    },
)
async def submit_platform_application(args: Dict[str, Any]) -> Dict[str, Any]:
    """Submit or decline consultation application using browser automation"""
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    project_url = args.get("project_url")
    platform_name = args.get("platform_name", "unknown")
    form_data = args.get("form_data", {})
    # Parse form_data if it's a JSON string, otherwise use as plain text
    if isinstance(form_data, str):
        # Try to parse as JSON first
        try:
            form_data = json.loads(form_data)
        except json.JSONDecodeError:
            # Not JSON - treat as plain text form content
            # This handles cases where the agent passes form responses directly
            logger.debug(f"[Correlation ID: {ctx.correlation_id}] form_data is plain text, using directly")
            form_data = {"text_content": form_data}
    login_username = args.get("login_username")
    login_password = args.get("login_password")
    decline = args.get("decline", False)
    max_retries = args.get("max_retries", 3)
    verification_prompt = args.get("verification_prompt", "Verify that the application was successfully submitted.")

    if not project_url:
        return {
            "content": [
                {"type": "text", "text": "project_url is required"}
            ],
            "is_error": True,
        }

    # Check for batch dashboard mode - process ALL invitations in ONE browser session
    if isinstance(form_data, dict) and form_data.get("mode") == "batch_dashboard":
        logger.info(f"[Correlation ID: {ctx.correlation_id}] Using BATCH DASHBOARD mode for {platform_name}")
        try:
            from ..browser.computer_use import BrowserAutomation
            from datetime import datetime
            from pathlib import Path
            
            profile_context = form_data.get("profile", {})
            if isinstance(profile_context, str):
                try:
                    profile_context = json.loads(profile_context)
                except json.JSONDecodeError:
                    profile_context = {"summary": profile_context}
            
            browser = BrowserAutomation(platform_name, ctx.correlation_id)
            processed_count, actions = await browser.process_dashboard_invitations(
                dashboard_url=project_url,
                login_username=login_username or "",
                login_password=login_password or "",
                profile_context=profile_context
            )
            
            # Save action log
            logs_dir = Path("logs/runs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            status = "success" if processed_count > 0 else "failure"
            log_file = logs_dir / f"{platform_name}_{timestamp}_batch_{status}.json"
            
            with open(log_file, "w") as f:
                json.dump(actions, f, indent=2, default=str)
            logger.info(f"[Correlation ID: {ctx.correlation_id}] Saved batch action log to {log_file}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": processed_count > 0,
                            "mode": "batch_dashboard",
                            "processed_count": processed_count,
                            "actions_taken": len(actions),
                            "log_file": str(log_file),
                            "message": f"Batch processed {processed_count} invitations in ONE browser session"
                        })
                    }
                ],
                "is_error": False,
            }
        except Exception as e:
            logger.error(f"[Correlation ID: {ctx.correlation_id}] Batch dashboard processing error: {e}")
            return {
                "content": [
                    {"type": "text", "text": f"Batch dashboard processing failed: {str(e)}"}
                ],
                "is_error": True,
            }

    try:
        # Import generic browser automation
        from ..browser.computer_use import submit_platform_application as submit_platform_application_impl
        from datetime import datetime
        from pathlib import Path

        # Get platform-specific configuration if available
        platform_config = None
        platform = ctx.platform_registry.get_platform(platform_name) if ctx.platform_registry else None
        if platform and hasattr(platform, 'get_platform_config'):
            platform_config = platform.get_platform_config()
            logger.debug(f"[Correlation ID: {ctx.correlation_id}] Using {platform_name} platform config")

        # Build task prompt (platform-specific prompt construction happens here)
        task_prompt = _build_task_prompt(
            platform_name=platform_name,
            project_url=project_url,
            form_data=form_data if not decline else {},
            login_username=login_username,
            login_password=login_password,
            decline=decline,
            platform_registry=ctx.platform_registry
        )

        # Submit or decline application using Claude (with Gemini fallback)
        result = await submit_platform_application_impl(
            project_url=project_url,
            task_prompt=task_prompt,
            platform_name=platform_name,
            max_retries=max_retries,
            verification_prompt=verification_prompt,
            platform_config=platform_config
        )

        # Save action log to a file
        logs_dir = Path("logs/runs")
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        status = "success" if result["success"] else "failure"
        log_file = logs_dir / f"{platform_name}_{timestamp}_{status}.json"
        with open(log_file, "w") as f:
            json.dump(result["actions"], f, indent=2)
        
        logger.info(f"[Correlation ID: {ctx.correlation_id}] Saved action log to {log_file}")

        if result["success"]:
            logger.success(f"[Correlation ID: {ctx.correlation_id}] {platform_name} application submitted via {result['method']}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": True,
                            "method": result["method"],
                            "actions_taken": len(result["actions"]),
                            "log_file": str(log_file),
                            "message": f"Successfully submitted via {result['method']}"
                        })
                    }
                ]
            }
        else:
            # Ensure error details are always present in submission_details for failed runs
            error_details = {
                "success": False,
                "error": result.get("error", "Unknown browser automation error"),
                "component": "browser_automation", # Default component for browser automation failures
                "actions_attempted": len(result.get("actions", [])),
                "log_file": str(log_file)
            }
            logger.error(f"[Correlation ID: {ctx.correlation_id}] {platform_name} application submission failed: {error_details['error']}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(error_details)
                    }
                ],
                "is_error": True,
            }

    except Exception as e:
        # Catch-all for exceptions during tool execution
        error_details = {
            "success": False,
            "error": f"Exception during submit_platform_application: {str(e)}",
            "component": "submit_platform_application_tool", # Component for tool-level exceptions
            "actions_attempted": 0
        }
        logger.error(f"[Correlation ID: {ctx.correlation_id}] Error submitting {platform_name} application: {e}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(error_details)
                }
            ],
            "is_error": True,
        }


@handle_tool_errors
@tool(
    "archive_email",
    "Archive a processed consultation email by removing it from the inbox",
    {"email_id": str},
)
async def archive_email(args: Dict[str, Any]) -> Dict[str, Any]:
    """Archive a consultation email after processing is complete"""
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    email_id = args.get("email_id")
    if not email_id:
        return {
            "content": [
                {"type": "text", "text": "email_id is required"}
            ],
            "is_error": True,
        }

    logger.info(f"[Correlation ID: {ctx.correlation_id}] Archiving email: {email_id}")

    try:
        # Use the Gmail client from email processor to archive the email
        ctx.email_processor.gmail.archive_email(email_id)

        # Record the archiving action in metrics
        ctx.metrics.record_email_archived()

        logger.info(f"[Correlation ID: {ctx.correlation_id}] Successfully archived email: {email_id}")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully archived email {email_id}",
                }
            ]
        }
    except Exception as exc:
        logger.error(f"[Correlation ID: {ctx.correlation_id}] Failed to archive email {email_id}: {exc}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to archive email {email_id}: {exc}",
                }
            ],
            "is_error": True,
        }


@handle_tool_errors
@tool(
    "finalize_run_and_report",
    "Finalize metrics for this run and generate a report",
    {},
)
async def finalize_run_and_report(args: Dict[str, Any]) -> Dict[str, Any]:
    global agent_ctx
    ctx = agent_ctx
    if ctx is None:
        return {
            "content": [
                {"type": "text", "text": "Agent context not initialized"}
            ],
            "is_error": True,
        }

    report = await ctx.reporter.generate_daily_report(send_email=True)
    metrics_summary = ctx.metrics.get_summary()

    logger.info(f"[Correlation ID: {ctx.correlation_id}] Finalizing run and generating report.")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "report": report,
                        "metrics": metrics_summary,
                    }
                ),
            }
        ]
    }


async def run_consult_agent(days_back: int, platform_filter: str = None, mode: str = "email") -> Dict[str, Any]:
    """Run the ConsultPipelineAgent loop via the Claude Agent SDK.

    This sets up a fresh agent context for the run and delegates
    control to the Agent SDK, which will use the defined tools.

    Args:
        days_back: Number of days to look back for emails
        platform_filter: Optional platform to focus on (e.g., 'glg', 'guidepoint')
        mode: Processing mode - 'email' (default) or 'dashboard' (batch process all invitations)
    """
    global agent_ctx
    from datetime import datetime, timedelta, timedelta

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    memory_store = MemoryStore()
    metrics = MetricsTracker()
    reporter = Reporter(memory_store, metrics)
    profile_aggregator = ProfileAggregator()
    platform_registry = PlatformRegistry()
    email_processor = EmailProcessor(memory_store=memory_store)

    agent_ctx = AgentContext(
        memory_store=memory_store,
        metrics=metrics,
        reporter=reporter,
        profile_aggregator=profile_aggregator,
        email_processor=email_processor,
        platform_registry=platform_registry,
        correlation_id=run_id,
    )

    server = create_sdk_mcp_server(
        name="consult",
        version="1.0.0",
        tools=[
            list_recent_consultation_emails,
            get_cp_writing_style,
            get_profile_summary,
            record_consultation_decision,
            archive_email,
            finalize_run_and_report,
            get_application_form_data,
            get_platform_login_info,
            send_email_reply,
            submit_platform_application,
        ],
    )

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"consult": server},
        allowed_tools=[
            "mcp__consult__list_recent_consultation_emails",
            "mcp__consult__get_cp_writing_style",
            "mcp__consult__get_profile_summary",
            "mcp__consult__record_consultation_decision",
            "mcp__consult__archive_email",
            "mcp__consult__finalize_run_and_report",
            "mcp__consult__get_application_form_data",
            "mcp__consult__get_platform_login_info",
            "mcp__consult__send_email_reply",
            "mcp__consult__submit_platform_application",
        ],
        env={"ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "")},
    )

    async with ClaudeSDKClient(options=options) as client:
        # Kick off the run. The agent will call tools as needed.
        if mode == "dashboard" and platform_filter:
            # DASHBOARD MODE: Batch process ALL invitations in ONE browser session
            auth_type = _get_platform_auth_type(platform_filter)
            query = f"""Process ALL {platform_filter.upper()} invitations in BATCH DASHBOARD mode:

1. Call get_platform_login_info to get dashboard_url and credentials
2. Call get_profile_summary to understand evaluation criteria
3. Call get_cp_writing_style to understand writing principles
4. Call submit_platform_application with:
   - project_url: the dashboard_url from step 1
   - platform_name: "{platform_filter}"
   - form_data: {{"mode": "batch_dashboard", "profile": "<include profile summary from step 2>"}}
   - login_username and login_password from step 1 (null for Google OAuth platforms)

CRITICAL: You MUST set form_data["mode"] = "batch_dashboard" to enable batch processing.
This will process ALL available invitations in ONE browser session.

The browser automation will:
- Login to the platform (using credentials or Google OAuth)
- Navigate to the dashboard
- Process ALL visible invitations/surveys one by one
- Complete each form using CP writing style and profile context
- Submit each response before moving to the next

5. Call finalize_run_and_report with summary of all processed invitations
"""
            logger.info(f"[Correlation ID: {run_id}] Starting DASHBOARD mode for {platform_filter.upper()} (batch processing)")
        elif platform_filter:
            # Check if this is a Google OAuth platform
            auth_type = _get_platform_auth_type(platform_filter)

            if auth_type == "google_oauth":
                # Google OAuth platforms (e.g., Office Hours) - no credentials needed
                query = f"""Process {platform_filter.upper()} opportunities using Google OAuth:

1. Call get_platform_login_info to get dashboard_url
   - NOTE: This platform uses Google OAuth, so username/password will be null - that's expected!
   - You only need the dashboard_url to proceed.
2. Call get_profile_summary to understand evaluation criteria
3. Call get_cp_writing_style to understand writing principles
4. Call submit_platform_application with:
   - project_url: the dashboard_url from step 1
   - platform_name: "{platform_filter}"
   - form_data: empty dict (the task prompt will guide the AI)
   - login_username: null (Google OAuth - no credentials needed)
   - login_password: null (Google OAuth - no credentials needed)

IMPORTANT: This platform uses Google OAuth for authentication:
- The browser profile already has the Google session saved
- The AI will click "Sign in with Google" button to authenticate
- NO username/password is required - proceed even if credentials are null

The AI will:
- Navigate to dashboard_url
- Click "Sign in with Google" to authenticate
- Complete available surveys using CP writing style
- Submit responses

5. Record the decision using record_consultation_decision
6. Call finalize_run_and_report
"""
            else:
                # Standard credential-based platforms (GLG, Guidepoint, Coleman)
                query = f"""Process {platform_filter.upper()} consultation opportunities:

1. Call get_platform_login_info to get dashboard_url and credentials
2. Call get_profile_summary to understand evaluation criteria
3. Call get_cp_writing_style to understand writing principles
4. Call submit_platform_application with:
   - project_url: the dashboard_url from step 1
   - platform_name: "{platform_filter}"
   - form_data: A task description for the AI to complete the first available invitation:
     "Login to {platform_filter.upper()} dashboard, click on the FIRST 'Complete Vetting Q&A' button,
      fill out the vetting questions using the profile context, complete all steps including
      rate confirmation and final submission. Use Tab key for navigation."
   - login_username and login_password from step 1

This will use Gemini Computer Use to:
- Login with provided credentials
- Navigate to dashboard
- Click the first available opportunity
- Complete the vetting form
- Submit the application

5. Record the decision using record_consultation_decision
6. Call finalize_run_and_report
"""
            logger.info(f"[Correlation ID: {run_id}] Starting Claude Agent SDK run for {platform_filter.upper()} ({auth_type}) processing")
        else:
            query = f"Process consultation emails from the last {days_back} days."
            logger.info(f"[Correlation ID: {run_id}] Starting Claude Agent SDK run for {days_back} days")
        await client.query(query)

        # Drain responses so the loop completes.
        message_count = 0
        async for message in client.receive_response():
            message_count += 1
            logger.info(f"[Correlation ID: {run_id}] Agent message {message_count}: {message}")
            # For now we do not stream these to stdout; logs are in tools.

        logger.info(f"[Correlation ID: {run_id}] Agent completed with {message_count} messages")

    # Build result structure
    metrics_summary = metrics.get_summary()
    
    # Save metrics to persistent store
    memory_store.save_run_metrics(run_id, metrics_summary)
    
    return metrics_summary
