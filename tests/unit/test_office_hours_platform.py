"""Unit tests for Office Hours platform implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.platforms.office_hours_platform import (
    OfficeHoursPlatform,
    OFFICE_HOURS_SUCCESS_INDICATORS,
    OFFICE_HOURS_FAILURE_INDICATORS,
    OFFICE_HOURS_BLOCKED_INDICATORS,
    OFFICE_HOURS_WORKFLOW_STAGES,
    build_office_hours_task_prompt,
    get_office_hours_platform_config,
)


class TestOfficeHoursPlatformInitialization:
    """Test OfficeHoursPlatform class initialization."""

    def test_platform_name(self):
        """Test platform is initialized with correct name."""
        platform = OfficeHoursPlatform()
        assert platform.name == "OfficeHours"

    def test_platform_inherits_base_platform(self):
        """Test platform inherits from BasePlatform."""
        from src.platforms.base import BasePlatform
        platform = OfficeHoursPlatform()
        assert isinstance(platform, BasePlatform)


class TestOfficeHoursIndicators:
    """Test success, failure, and blocked indicators."""

    def test_success_indicators_not_empty(self):
        """Test success indicators list is populated."""
        assert len(OFFICE_HOURS_SUCCESS_INDICATORS) > 0

    def test_success_indicators_contain_expected_phrases(self):
        """Test success indicators contain expected success messages."""
        expected_phrases = [
            "thank you for completing",
            "survey submitted",
        ]
        for phrase in expected_phrases:
            assert phrase in OFFICE_HOURS_SUCCESS_INDICATORS

    def test_failure_indicators_not_empty(self):
        """Test failure indicators list is populated."""
        assert len(OFFICE_HOURS_FAILURE_INDICATORS) > 0

    def test_failure_indicators_contain_expected_phrases(self):
        """Test failure indicators contain expected error messages."""
        expected_phrases = [
            "error submitting",
            "something went wrong",
        ]
        for phrase in expected_phrases:
            assert phrase in OFFICE_HOURS_FAILURE_INDICATORS

    def test_blocked_indicators_not_empty(self):
        """Test blocked indicators list is populated."""
        assert len(OFFICE_HOURS_BLOCKED_INDICATORS) > 0

    def test_blocked_indicators_contain_expected_phrases(self):
        """Test blocked indicators contain expected blocked messages."""
        expected_phrases = [
            "survey closed",
            "already completed",
        ]
        for phrase in expected_phrases:
            assert phrase in OFFICE_HOURS_BLOCKED_INDICATORS


class TestOfficeHoursWorkflowStages:
    """Test workflow stages definition."""

    def test_workflow_stages_has_required_keys(self):
        """Test workflow stages contains all required survey sections."""
        required_stages = [
            "survey_intro",
            "questions",
            "completion",
        ]
        for stage in required_stages:
            assert stage in OFFICE_HOURS_WORKFLOW_STAGES

    def test_each_stage_has_keywords(self):
        """Test each workflow stage has at least one keyword."""
        for stage, keywords in OFFICE_HOURS_WORKFLOW_STAGES.items():
            assert len(keywords) > 0, f"Stage {stage} has no keywords"
            assert all(isinstance(k, str) for k in keywords)


class TestOfficeHoursPlatformConfig:
    """Test platform configuration generation."""

    def test_get_platform_config_returns_dict(self):
        """Test platform config returns a dictionary."""
        config = get_office_hours_platform_config()
        assert isinstance(config, dict)

    def test_config_contains_required_keys(self):
        """Test platform config contains all required keys."""
        config = get_office_hours_platform_config()
        required_keys = [
            "success_indicators",
            "failure_indicators",
            "blocked_indicators",
            "workflow_stages",
            "dialog_handler",
            "cookie_selectors",
            "login_type",
            "uses_browser_profile",
        ]
        for key in required_keys:
            assert key in config

    def test_config_dialog_handler_is_callable(self):
        """Test dialog handler in config is callable."""
        config = get_office_hours_platform_config()
        assert callable(config["dialog_handler"])

    def test_config_login_type_is_google_oauth(self):
        """Test login type is set to Google OAuth."""
        config = get_office_hours_platform_config()
        assert config["login_type"] == "google_oauth"

    def test_config_uses_browser_profile(self):
        """Test platform uses browser profile for authentication."""
        config = get_office_hours_platform_config()
        assert config["uses_browser_profile"] is True


class TestOfficeHoursGoogleAuth:
    """Test Google OAuth configuration specifics."""

    def test_platform_config_identifies_oauth_login(self):
        """Test platform config correctly identifies OAuth login type."""
        platform = OfficeHoursPlatform()
        config = platform.get_platform_config()
        assert config["login_type"] == "google_oauth"

    def test_platform_uses_persistent_browser_profile(self):
        """Test platform relies on persistent browser profile."""
        platform = OfficeHoursPlatform()
        config = platform.get_platform_config()
        assert config["uses_browser_profile"] is True

    def test_task_prompt_does_not_include_credentials(self):
        """Test task prompt doesn't include username/password for OAuth."""
        form_data = {"survey_responses": "Test response"}
        prompt = build_office_hours_task_prompt(
            form_data,
            login_username="ignored@gmail.com",
            login_password="ignored_password",
            decline=False
        )
        # OAuth uses browser profile, so credentials should NOT appear in prompt
        # The function accepts them but doesn't use them
        assert "ignored_password" not in prompt

    def test_task_prompt_mentions_google_oauth(self):
        """Test task prompt mentions Google OAuth authentication."""
        form_data = {}
        prompt = build_office_hours_task_prompt(form_data, decline=False)
        assert "Google" in prompt
        assert "Sign in with Google" in prompt
        assert "NOT username/password" in prompt or "no username/password" in prompt.lower()


class TestBuildOfficeHoursTaskPrompt:
    """Test task prompt generation for browser automation."""

    def test_accept_prompt_contains_survey_instructions(self):
        """Test accept prompt includes survey completion instructions."""
        form_data = {"survey_responses": "My survey answers"}
        prompt = build_office_hours_task_prompt(form_data, decline=False)

        # Check for key survey instructions
        assert "survey" in prompt.lower()
        assert "Complete Survey" in prompt or "submit" in prompt.lower()

    def test_accept_prompt_includes_form_data(self):
        """Test accept prompt includes the form data fields."""
        form_data = {
            "survey_responses": "Expert perspective on training",
            "topic": "Professional certification",
        }
        prompt = build_office_hours_task_prompt(form_data, decline=False)

        assert "survey_responses" in prompt
        assert "Expert perspective on training" in prompt

    def test_accept_prompt_without_login_credentials(self):
        """Test accept prompt works without credentials (Google OAuth)."""
        form_data = {"survey_responses": "Test"}
        prompt = build_office_hours_task_prompt(
            form_data,
            login_username=None,
            login_password=None,
            decline=False
        )

        # Should still work and mention Google OAuth
        assert "Google" in prompt
        assert isinstance(prompt, str)

    def test_decline_prompt_is_different(self):
        """Test decline prompt has different instructions."""
        form_data = {"survey_responses": "Test"}
        accept_prompt = build_office_hours_task_prompt(form_data, decline=False)
        decline_prompt = build_office_hours_task_prompt(form_data, decline=True)

        assert "DECLINE" in decline_prompt
        # Decline should not have full survey completion instructions
        assert "Complete Survey" not in decline_prompt

    def test_prompt_handles_text_content_field(self):
        """Test prompt handles text_content field specially."""
        form_data = {"text_content": "This is raw text content for the survey"}
        prompt = build_office_hours_task_prompt(form_data, decline=False)

        assert "This is raw text content for the survey" in prompt

    def test_prompt_contains_never_wait_instruction(self):
        """Test prompt emphasizes autonomous operation."""
        form_data = {"survey_responses": "Test"}
        prompt = build_office_hours_task_prompt(form_data, decline=False)

        assert "NEVER WAIT FOR HUMAN INPUT" in prompt

    def test_prompt_mentions_cp_writing_style(self):
        """Test prompt references CP writing style for responses."""
        form_data = {}
        prompt = build_office_hours_task_prompt(form_data, decline=False)

        assert "CP writing style" in prompt

    def test_prompt_handles_empty_form_data(self):
        """Test prompt handles empty form data gracefully."""
        prompt = build_office_hours_task_prompt({}, decline=False)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestOfficeHoursPlatformPrepareApplication:
    """Test prepare_application method."""

    @pytest.mark.asyncio
    async def test_prepare_application_returns_dict(self):
        """Test prepare_application returns a dictionary."""
        platform = OfficeHoursPlatform()
        result = await platform.prepare_application({})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_prepare_application_has_required_keys(self):
        """Test prepare_application result has required structure."""
        platform = OfficeHoursPlatform()
        result = await platform.prepare_application({})

        assert "fields" in result
        assert "office_hours_specific" in result
        assert "context" in result

    @pytest.mark.asyncio
    async def test_prepare_application_fields_structure(self):
        """Test fields in prepare_application have proper structure."""
        platform = OfficeHoursPlatform()
        result = await platform.prepare_application({})

        fields = result["fields"]
        assert "survey_responses" in fields

        # Each field should have type and purpose
        for field_name, field_def in fields.items():
            assert "type" in field_def
            assert "purpose" in field_def

    @pytest.mark.asyncio
    async def test_prepare_application_uses_profile_context(self):
        """Test prepare_application includes profile context."""
        platform = OfficeHoursPlatform()
        consultation_data = {
            "profile_context": {"name": "Test User", "expertise": ["Training", "Certification"]},
            "project_description": "Survey about professional certifications",
        }
        result = await platform.prepare_application(consultation_data)

        assert result["context"]["profile_context"]["name"] == "Test User"
        assert result["context"]["project_description"] == "Survey about professional certifications"

    @pytest.mark.asyncio
    async def test_prepare_application_includes_office_hours_specifics(self):
        """Test prepare_application includes Office Hours-specific config."""
        platform = OfficeHoursPlatform()
        result = await platform.prepare_application({})

        office_hours_specific = result["office_hours_specific"]
        assert "workflow_stages" in office_hours_specific
        assert "success_indicators" in office_hours_specific
        assert "login_type" in office_hours_specific
        assert office_hours_specific["login_type"] == "google_oauth"
        assert office_hours_specific["uses_browser_profile"] is True


class TestOfficeHoursPlatformBuildTaskPrompt:
    """Test build_task_prompt method on platform class."""

    def test_build_task_prompt_delegates_correctly(self):
        """Test build_task_prompt delegates to module function."""
        platform = OfficeHoursPlatform()
        form_data = {"survey_responses": "Test responses"}

        result = platform.build_task_prompt(
            form_data=form_data,
            login_username=None,
            login_password=None,
            decline=False
        )

        assert isinstance(result, str)
        assert "Test responses" in result

    def test_build_task_prompt_decline(self):
        """Test build_task_prompt generates decline instructions."""
        platform = OfficeHoursPlatform()
        result = platform.build_task_prompt(
            form_data={},
            decline=True
        )

        assert "DECLINE" in result


class TestOfficeHoursPlatformGetConfig:
    """Test get_platform_config method on platform class."""

    def test_get_platform_config_returns_expected_structure(self):
        """Test get_platform_config returns proper config dict."""
        platform = OfficeHoursPlatform()
        config = platform.get_platform_config()

        assert isinstance(config, dict)
        assert "success_indicators" in config
        assert "failure_indicators" in config
        assert "workflow_stages" in config
        assert "login_type" in config


class TestOfficeHoursPlatformIntegration:
    """Integration tests for platform with registry."""

    def test_platform_registered_in_registry(self):
        """Test Office Hours platform is properly registered."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()
        platform = registry.get_platform("office_hours")

        assert platform is not None
        assert isinstance(platform, OfficeHoursPlatform)

    def test_platform_detection_from_email_officehours_sender(self):
        """Test platform detection from officehours in sender."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "noreply@officehours.com",
            "subject": "Paid Survey Opportunity",
            "bodyText": "Complete this survey...",
        }
        assert registry.detect_platform(email) == "office_hours"

    def test_platform_detection_from_email_kai_seed_sender(self):
        """Test platform detection from Kai Seed sender."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "kai.seed@officehours.com",
            "subject": "Survey Request",
            "bodyText": "Details...",
        }
        assert registry.detect_platform(email) == "office_hours"

    def test_platform_detection_from_body_url(self):
        """Test platform detection from officehours.com URL in body."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        email = {
            "sender_email": "someone@example.com",
            "subject": "Survey",
            "bodyText": "Click here: https://officehours.com/survey/123",
        }
        assert registry.detect_platform(email) == "office_hours"

    def test_platform_not_confused_with_glg(self):
        """Test Office Hours is not confused with GLG platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        glg_email = {
            "sender_email": "noreply@glgroup.com",
            "subject": "GLG Project",
            "bodyText": "GLG consultation details",
        }
        assert registry.detect_platform(glg_email) == "glg"

    def test_platform_not_confused_with_guidepoint(self):
        """Test Office Hours is not confused with Guidepoint platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        guidepoint_email = {
            "sender_email": "noreply@guidepointglobal.com",
            "subject": "Guidepoint Request",
            "bodyText": "Guidepoint details",
        }
        assert registry.detect_platform(guidepoint_email) == "guidepoint"

    def test_platform_not_confused_with_coleman(self):
        """Test Office Hours is not confused with Coleman platform."""
        from src.platforms.registry import PlatformRegistry

        registry = PlatformRegistry()

        coleman_email = {
            "sender_email": "noreply@coleman.colemanerm.com",
            "subject": "Coleman Request",
            "bodyText": "Coleman details",
        }
        assert registry.detect_platform(coleman_email) == "coleman"
