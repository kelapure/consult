"""Unit tests for Coleman platform implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.platforms.coleman_platform import (
    ColemanPlatform,
    COLEMAN_SUCCESS_INDICATORS,
    COLEMAN_FAILURE_INDICATORS,
    COLEMAN_BLOCKED_INDICATORS,
    COLEMAN_WORKFLOW_STAGES,
    COLEMAN_VETTING_DEFAULTS,
    build_coleman_task_prompt,
    get_coleman_platform_config,
)


class TestColemanPlatformInitialization:
    """Test ColemanPlatform class initialization."""

    def test_platform_name(self):
        """Test platform is initialized with correct name."""
        platform = ColemanPlatform()
        assert platform.name == "Coleman"

    def test_platform_inherits_base_platform(self):
        """Test platform inherits from BasePlatform."""
        from src.platforms.base import BasePlatform
        platform = ColemanPlatform()
        assert isinstance(platform, BasePlatform)


class TestColemanIndicators:
    """Test success, failure, and blocked indicators."""

    def test_success_indicators_not_empty(self):
        """Test success indicators list is populated."""
        assert len(COLEMAN_SUCCESS_INDICATORS) > 0

    def test_success_indicators_contain_expected_phrases(self):
        """Test success indicators contain expected success messages."""
        expected_phrases = [
            "you're all set",
            "wait for your research manager",
        ]
        for phrase in expected_phrases:
            assert phrase in COLEMAN_SUCCESS_INDICATORS

    def test_failure_indicators_not_empty(self):
        """Test failure indicators list is populated."""
        assert len(COLEMAN_FAILURE_INDICATORS) > 0

    def test_failure_indicators_contain_expected_phrases(self):
        """Test failure indicators contain expected error messages."""
        expected_phrases = [
            "an error occurred",
            "something went wrong",
        ]
        for phrase in expected_phrases:
            assert phrase in COLEMAN_FAILURE_INDICATORS

    def test_blocked_indicators_not_empty(self):
        """Test blocked indicators list is populated."""
        assert len(COLEMAN_BLOCKED_INDICATORS) > 0

    def test_blocked_indicators_contain_expected_phrases(self):
        """Test blocked indicators contain expected blocked messages."""
        expected_phrases = [
            "already completed",
            "request expired",
        ]
        for phrase in expected_phrases:
            assert phrase in COLEMAN_BLOCKED_INDICATORS


class TestColemanWorkflowStages:
    """Test workflow stages definition."""

    def test_workflow_stages_has_required_keys(self):
        """Test workflow stages contains all required form sections."""
        required_stages = [
            "vetting_questions",
            "rate_limit",
            "complete_vetting",
            "completion",
        ]
        for stage in required_stages:
            assert stage in COLEMAN_WORKFLOW_STAGES

    def test_each_stage_has_keywords(self):
        """Test each workflow stage has at least one keyword."""
        for stage, keywords in COLEMAN_WORKFLOW_STAGES.items():
            assert len(keywords) > 0, f"Stage {stage} has no keywords"
            assert all(isinstance(k, str) for k in keywords)


class TestColemanVettingDefaults:
    """Test vetting question defaults."""

    def test_has_default_key(self):
        """Test vetting defaults has a default fallback."""
        assert "default" in COLEMAN_VETTING_DEFAULTS

    def test_default_answer_is_yes(self):
        """Test default answer is Yes."""
        assert COLEMAN_VETTING_DEFAULTS["default"]["answer"] == "Yes"


class TestColemanPlatformConfig:
    """Test platform configuration generation."""

    def test_get_platform_config_returns_dict(self):
        """Test platform config returns a dictionary."""
        config = get_coleman_platform_config()
        assert isinstance(config, dict)

    def test_config_contains_required_keys(self):
        """Test platform config contains all required keys."""
        config = get_coleman_platform_config()
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
        config = get_coleman_platform_config()
        assert callable(config["dialog_handler"])


class TestBuildColemanTaskPrompt:
    """Test task prompt generation for browser automation."""

    def test_accept_prompt_contains_workflow_steps(self):
        """Test accept prompt includes all workflow steps."""
        form_data = {"thoughts_on_subject": "My expertise in AI/ML"}
        prompt = build_coleman_task_prompt(form_data, decline=False)

        # Check for key workflow instructions
        assert "Vetting Questions" in prompt
        assert "Rate Limit" in prompt
        assert "COMPLETE VETTING" in prompt
        assert "You're all set" in prompt

    def test_accept_prompt_includes_form_data(self):
        """Test accept prompt includes the form data fields."""
        form_data = {
            "thoughts_on_subject": "Expert perspective on data centers",
            "rate_limit_confirmation": "All Good",
        }
        prompt = build_coleman_task_prompt(form_data, decline=False)

        assert "thoughts_on_subject" in prompt
        assert "Expert perspective on data centers" in prompt

    def test_accept_prompt_with_login_credentials(self):
        """Test accept prompt includes login instructions when credentials provided."""
        form_data = {"thoughts_on_subject": "Test"}
        prompt = build_coleman_task_prompt(
            form_data,
            login_username="testuser@gmail.com",
            login_password="testpass",
            decline=False
        )

        assert "login" in prompt.lower()
        assert "testuser@gmail.com" in prompt
        assert "testpass" in prompt

    def test_decline_prompt_is_different(self):
        """Test decline prompt has different instructions."""
        form_data = {"thoughts_on_subject": "Test"}
        accept_prompt = build_coleman_task_prompt(form_data, decline=False)
        decline_prompt = build_coleman_task_prompt(form_data, decline=True)

        assert "DECLINE" in decline_prompt
        assert "Decline Vetting Q&A" in decline_prompt
        # Decline should not have the full workflow
        assert "Rate Limit" not in decline_prompt

    def test_decline_prompt_with_login_credentials(self):
        """Test decline prompt includes login when credentials provided."""
        form_data = {}
        prompt = build_coleman_task_prompt(
            form_data,
            login_username="user@email.com",
            login_password="pass",
            decline=True
        )

        assert "login" in prompt.lower()
        assert "user@email.com" in prompt

    def test_prompt_handles_text_content_field(self):
        """Test prompt handles text_content field specially."""
        form_data = {"text_content": "This is raw text content for the form"}
        prompt = build_coleman_task_prompt(form_data, decline=False)

        assert "This is raw text content for the form" in prompt

    def test_prompt_contains_never_wait_instruction(self):
        """Test prompt emphasizes autonomous operation."""
        form_data = {"thoughts_on_subject": "Test"}
        prompt = build_coleman_task_prompt(form_data, decline=False)

        assert "NEVER WAIT FOR HUMAN INPUT" in prompt


class TestColemanPlatformPrepareApplication:
    """Test prepare_application method."""

    @pytest.mark.asyncio
    async def test_prepare_application_returns_dict(self):
        """Test prepare_application returns a dictionary."""
        platform = ColemanPlatform()
        result = await platform.prepare_application({})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_prepare_application_has_required_keys(self):
        """Test prepare_application result has required structure."""
        platform = ColemanPlatform()
        result = await platform.prepare_application({})

        assert "fields" in result
        assert "coleman_specific" in result
        assert "context" in result

    @pytest.mark.asyncio
    async def test_prepare_application_fields_structure(self):
        """Test fields in prepare_application have proper structure."""
        platform = ColemanPlatform()
        result = await platform.prepare_application({})

        fields = result["fields"]
        assert "thoughts_on_subject" in fields
        assert "rate_limit_confirmation" in fields

        # Each field should have type and purpose
        for field_name, field_def in fields.items():
            assert "type" in field_def
            assert "purpose" in field_def

    @pytest.mark.asyncio
    async def test_prepare_application_uses_profile_context(self):
        """Test prepare_application includes profile context."""
        platform = ColemanPlatform()
        consultation_data = {
            "profile_context": {"name": "Test User", "expertise": ["AI", "ML"]},
            "project_description": "Data center consultation project",
        }
        result = await platform.prepare_application(consultation_data)

        assert result["context"]["profile_context"]["name"] == "Test User"
        assert result["context"]["project_description"] == "Data center consultation project"

    @pytest.mark.asyncio
    async def test_prepare_application_includes_coleman_specifics(self):
        """Test prepare_application includes Coleman-specific config."""
        platform = ColemanPlatform()
        result = await platform.prepare_application({})

        coleman_specific = result["coleman_specific"]
        assert "vetting_defaults" in coleman_specific
        assert "workflow_stages" in coleman_specific
        assert "success_indicators" in coleman_specific


class TestColemanPlatformBuildTaskPrompt:
    """Test build_task_prompt method on platform class."""

    def test_build_task_prompt_delegates_correctly(self):
        """Test build_task_prompt delegates to module function."""
        platform = ColemanPlatform()
        form_data = {"thoughts_on_subject": "Test thoughts"}

        result = platform.build_task_prompt(
            form_data=form_data,
            login_username="user@email.com",
            login_password="pass",
            decline=False
        )

        assert isinstance(result, str)
        assert "Test thoughts" in result
        assert "user@email.com" in result

    def test_build_task_prompt_decline(self):
        """Test build_task_prompt generates decline instructions."""
        platform = ColemanPlatform()
        result = platform.build_task_prompt(
            form_data={},
            decline=True
        )

        assert "DECLINE" in result


class TestColemanPlatformGetConfig:
    """Test get_platform_config method on platform class."""

    def test_get_platform_config_returns_expected_structure(self):
        """Test get_platform_config returns proper config dict."""
        platform = ColemanPlatform()
        config = platform.get_platform_config()

        assert isinstance(config, dict)
        assert "success_indicators" in config
        assert "failure_indicators" in config
        assert "workflow_stages" in config


class TestColemanPlatformIntegration:
    """Integration tests for platform with registry."""

    def test_platform_registered_in_registry(self):
        """Test Coleman platform is properly registered."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()
        platform = registry.get_platform("coleman")

        assert platform is not None
        assert isinstance(platform, ColemanPlatform)

    def test_platform_detection_from_email_coleman_sender(self):
        """Test platform detection from Coleman in sender."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "noreply@coleman.colemanerm.com",
            "subject": "Consultation Request",
            "bodyText": "Project details...",
        }
        assert registry.detect_platform(email) == "coleman"

    def test_platform_detection_from_email_visasq_sender(self):
        """Test platform detection from VISASQ in sender."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "notifications@visasq.com",
            "subject": "New Request",
            "bodyText": "Details...",
        }
        assert registry.detect_platform(email) == "coleman"

    def test_platform_detection_from_email_subject(self):
        """Test platform detection from Coleman in subject."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "someone@example.com",
            "subject": "Following-up on New Request from VISASQ/Coleman: Data Center Project",
            "bodyText": "Details...",
        }
        assert registry.detect_platform(email) == "coleman"

    def test_platform_not_confused_with_glg(self):
        """Test Coleman is not confused with GLG platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        glg_email = {
            "sender_email": "noreply@glgroup.com",
            "subject": "GLG Project",
            "bodyText": "GLG consultation details",
        }
        assert registry.detect_platform(glg_email) == "glg"

    def test_platform_not_confused_with_guidepoint(self):
        """Test Coleman is not confused with Guidepoint platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        guidepoint_email = {
            "sender_email": "noreply@guidepointglobal.com",
            "subject": "Guidepoint Request",
            "bodyText": "Guidepoint details",
        }
        assert registry.detect_platform(guidepoint_email) == "guidepoint"
