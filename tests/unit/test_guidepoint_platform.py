"""Unit tests for Guidepoint platform implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.platforms.guidepoint_platform import (
    GuidepointPlatform,
    GUIDEPOINT_SUCCESS_INDICATORS,
    GUIDEPOINT_FAILURE_INDICATORS,
    GUIDEPOINT_BLOCKED_INDICATORS,
    GUIDEPOINT_WORKFLOW_STAGES,
    GUIDEPOINT_CLIENT_SCREENING_STRATEGY,
    build_guidepoint_task_prompt,
    get_guidepoint_platform_config,
)


class TestGuidepointPlatformInitialization:
    """Test GuidepointPlatform class initialization."""

    def test_platform_name(self):
        """Test platform is initialized with correct name."""
        platform = GuidepointPlatform()
        assert platform.name == "Guidepoint"

    def test_platform_inherits_base_platform(self):
        """Test platform inherits from BasePlatform."""
        from src.platforms.base import BasePlatform
        platform = GuidepointPlatform()
        assert isinstance(platform, BasePlatform)


class TestGuidepointIndicators:
    """Test success, failure, and blocked indicators."""

    def test_success_indicators_not_empty(self):
        """Test success indicators list is populated."""
        assert len(GUIDEPOINT_SUCCESS_INDICATORS) > 0

    def test_success_indicators_contain_expected_phrases(self):
        """Test success indicators contain expected success messages."""
        expected_phrases = [
            "thank you for your response",
            "successfully submitted",
            "submission complete",
        ]
        for phrase in expected_phrases:
            assert phrase in GUIDEPOINT_SUCCESS_INDICATORS

    def test_failure_indicators_not_empty(self):
        """Test failure indicators list is populated."""
        assert len(GUIDEPOINT_FAILURE_INDICATORS) > 0

    def test_failure_indicators_contain_expected_phrases(self):
        """Test failure indicators contain expected error messages."""
        expected_phrases = [
            "request has expired",
            "an error occurred",
            "something went wrong",
        ]
        for phrase in expected_phrases:
            assert phrase in GUIDEPOINT_FAILURE_INDICATORS

    def test_blocked_indicators_not_empty(self):
        """Test blocked indicators list is populated."""
        assert len(GUIDEPOINT_BLOCKED_INDICATORS) > 0

    def test_blocked_indicators_contain_expected_phrases(self):
        """Test blocked indicators contain expected blocked messages."""
        expected_phrases = [
            "already responded",
            "request expired",
            "link has expired",
        ]
        for phrase in expected_phrases:
            assert phrase in GUIDEPOINT_BLOCKED_INDICATORS


class TestGuidepointWorkflowStages:
    """Test workflow stages definition."""

    def test_workflow_stages_has_required_keys(self):
        """Test workflow stages contains all required form sections."""
        required_stages = [
            "rate_limit",
            "ai_agreement",
            "client_screening",
            "expert_screening",
            "compliance",
            "final_submit",
            "completion",
        ]
        for stage in required_stages:
            assert stage in GUIDEPOINT_WORKFLOW_STAGES

    def test_each_stage_has_keywords(self):
        """Test each workflow stage has at least one keyword."""
        for stage, keywords in GUIDEPOINT_WORKFLOW_STAGES.items():
            assert len(keywords) > 0, f"Stage {stage} has no keywords"
            assert all(isinstance(k, str) for k in keywords)


class TestGuidepointClientScreeningStrategy:
    """Test client screening question defaults."""

    def test_has_all_screening_fields(self):
        """Test client screening strategy has all required fields."""
        required_fields = ["senior_role", "employer", "title", "profile_updated"]
        for field in required_fields:
            assert field in GUIDEPOINT_CLIENT_SCREENING_STRATEGY

    def test_senior_role_defaults_to_no(self):
        """Test senior role default answer is No."""
        assert GUIDEPOINT_CLIENT_SCREENING_STRATEGY["senior_role"]["answer"] == "No"

    def test_profile_updated_defaults_to_yes(self):
        """Test profile updated default answer is Yes."""
        assert GUIDEPOINT_CLIENT_SCREENING_STRATEGY["profile_updated"]["answer"] == "Yes"


class TestGuidepointPlatformConfig:
    """Test platform configuration generation."""

    def test_get_platform_config_returns_dict(self):
        """Test platform config returns a dictionary."""
        config = get_guidepoint_platform_config()
        assert isinstance(config, dict)

    def test_config_contains_required_keys(self):
        """Test platform config contains all required keys."""
        config = get_guidepoint_platform_config()
        required_keys = [
            "success_indicators",
            "failure_indicators",
            "blocked_indicators",
            "workflow_stages",
            "dialog_handler",
            "cookie_selectors",
        ]
        for key in required_keys:
            assert key in config

    def test_config_dialog_handler_is_callable(self):
        """Test dialog handler in config is callable."""
        config = get_guidepoint_platform_config()
        assert callable(config["dialog_handler"])


class TestBuildGuidepointTaskPrompt:
    """Test task prompt generation for browser automation."""

    def test_accept_prompt_contains_workflow_steps(self):
        """Test accept prompt includes all workflow steps."""
        form_data = {"employer": "Test Company", "title": "Engineer"}
        prompt = build_guidepoint_task_prompt(form_data, decline=False)

        # Check for key workflow instructions
        assert "Rate Limit Acceptance" in prompt
        assert "AI Tools Agreement" in prompt
        assert "Client Review Screening" in prompt
        assert "Industry Expert Screening" in prompt
        assert "Compliance Checkboxes" in prompt
        assert "SUBMIT" in prompt

    def test_accept_prompt_includes_form_data(self):
        """Test accept prompt includes the form data fields."""
        form_data = {
            "employer": "Acme Corp",
            "title": "Senior Consultant",
            "experience": "10 years in AI/ML",
        }
        prompt = build_guidepoint_task_prompt(form_data, decline=False)

        assert "employer" in prompt
        assert "Acme Corp" in prompt
        assert "title" in prompt
        assert "Senior Consultant" in prompt

    def test_accept_prompt_with_login_credentials(self):
        """Test accept prompt includes login instructions when credentials provided."""
        form_data = {"employer": "Test"}
        prompt = build_guidepoint_task_prompt(
            form_data,
            login_username="testuser",
            login_password="testpass",
            decline=False
        )

        assert "login" in prompt.lower()
        assert "testuser" in prompt
        assert "testpass" in prompt

    def test_decline_prompt_is_different(self):
        """Test decline prompt has different instructions."""
        form_data = {"employer": "Test"}
        accept_prompt = build_guidepoint_task_prompt(form_data, decline=False)
        decline_prompt = build_guidepoint_task_prompt(form_data, decline=True)

        assert "DECLINE" in decline_prompt
        assert "I do not agree" in decline_prompt
        # Decline should not have the full workflow
        assert "Industry Expert Screening" not in decline_prompt

    def test_decline_prompt_with_login_credentials(self):
        """Test decline prompt includes login when credentials provided."""
        form_data = {}
        prompt = build_guidepoint_task_prompt(
            form_data,
            login_username="user",
            login_password="pass",
            decline=True
        )

        assert "login" in prompt.lower()
        assert "user" in prompt

    def test_prompt_handles_text_content_field(self):
        """Test prompt handles text_content field specially."""
        form_data = {"text_content": "This is raw text content for the form"}
        prompt = build_guidepoint_task_prompt(form_data, decline=False)

        assert "This is raw text content for the form" in prompt

    def test_prompt_contains_never_wait_instruction(self):
        """Test prompt emphasizes autonomous operation."""
        form_data = {"employer": "Test"}
        prompt = build_guidepoint_task_prompt(form_data, decline=False)

        assert "NEVER WAIT FOR HUMAN INPUT" in prompt


class TestGuidepointPlatformPrepareApplication:
    """Test prepare_application method."""

    @pytest.mark.asyncio
    async def test_prepare_application_returns_dict(self):
        """Test prepare_application returns a dictionary."""
        platform = GuidepointPlatform()
        result = await platform.prepare_application({})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_prepare_application_has_required_keys(self):
        """Test prepare_application result has required structure."""
        platform = GuidepointPlatform()
        result = await platform.prepare_application({})

        assert "fields" in result
        assert "guidepoint_specific" in result
        assert "context" in result

    @pytest.mark.asyncio
    async def test_prepare_application_fields_structure(self):
        """Test fields in prepare_application have proper structure."""
        platform = GuidepointPlatform()
        result = await platform.prepare_application({})

        fields = result["fields"]
        assert "employer" in fields
        assert "title" in fields
        assert "experience_summary" in fields

        # Each field should have type and purpose
        for field_name, field_def in fields.items():
            assert "type" in field_def
            assert "purpose" in field_def

    @pytest.mark.asyncio
    async def test_prepare_application_uses_profile_context(self):
        """Test prepare_application includes profile context."""
        platform = GuidepointPlatform()
        consultation_data = {
            "profile_context": {"name": "Test User", "expertise": ["AI", "ML"]},
            "project_description": "AI consultation project",
        }
        result = await platform.prepare_application(consultation_data)

        assert result["context"]["profile_context"]["name"] == "Test User"
        assert result["context"]["project_description"] == "AI consultation project"

    @pytest.mark.asyncio
    async def test_prepare_application_includes_guidepoint_specifics(self):
        """Test prepare_application includes Guidepoint-specific config."""
        platform = GuidepointPlatform()
        result = await platform.prepare_application({})

        gp_specific = result["guidepoint_specific"]
        assert "client_screening_strategy" in gp_specific
        assert "workflow_stages" in gp_specific
        assert "success_indicators" in gp_specific
        assert gp_specific["rate_limit_action"] == "accept"
        assert gp_specific["ai_agreement_action"] == "agree"


class TestGuidepointPlatformBuildTaskPrompt:
    """Test build_task_prompt method on platform class."""

    def test_build_task_prompt_delegates_correctly(self):
        """Test build_task_prompt delegates to module function."""
        platform = GuidepointPlatform()
        form_data = {"employer": "Test Co"}

        result = platform.build_task_prompt(
            form_data=form_data,
            login_username="user",
            login_password="pass",
            decline=False
        )

        assert isinstance(result, str)
        assert "Test Co" in result
        assert "user" in result

    def test_build_task_prompt_decline(self):
        """Test build_task_prompt generates decline instructions."""
        platform = GuidepointPlatform()
        result = platform.build_task_prompt(
            form_data={},
            decline=True
        )

        assert "DECLINE" in result


class TestGuidepointPlatformGetConfig:
    """Test get_platform_config method on platform class."""

    def test_get_platform_config_returns_expected_structure(self):
        """Test get_platform_config returns proper config dict."""
        platform = GuidepointPlatform()
        config = platform.get_platform_config()

        assert isinstance(config, dict)
        assert "success_indicators" in config
        assert "failure_indicators" in config
        assert "workflow_stages" in config


class TestGuidepointPlatformIntegration:
    """Integration tests for platform with registry."""

    def test_platform_registered_in_registry(self):
        """Test Guidepoint platform is properly registered."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()
        platform = registry.get_platform("guidepoint")

        assert platform is not None
        assert isinstance(platform, GuidepointPlatform)

    def test_platform_detection_from_email(self):
        """Test platform detection from email content."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        # Test with guidepoint in sender
        email_sender = {
            "sender_email": "noreply@guidepointglobal.com",
            "subject": "Consultation Request",
            "bodyText": "Project details...",
        }
        assert registry.detect_platform(email_sender) == "guidepoint"

        # Test with guidepoint in subject
        email_subject = {
            "sender_email": "someone@example.com",
            "subject": "Guidepoint Project Opportunity",
            "bodyText": "Details...",
        }
        assert registry.detect_platform(email_subject) == "guidepoint"

    def test_platform_not_confused_with_glg(self):
        """Test Guidepoint is not confused with GLG platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        # GLG email should not detect as Guidepoint
        glg_email = {
            "sender_email": "noreply@glgroup.com",
            "subject": "GLG Project",
            "bodyText": "GLG consultation details",
        }
        assert registry.detect_platform(glg_email) == "glg"

