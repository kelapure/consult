"""Integration tests for agent archiving workflow."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.agent.consult_agent import (
    run_consult_agent,
    AgentContext,
    list_recent_consultation_emails,
    record_consultation_decision,
    archive_email,
    finalize_run_and_report,
)


class TestAgentArchivingWorkflow:
    """Test complete agent workflow including archiving functionality."""

    @pytest.fixture
    def mock_consultation_emails(self):
        """Mock consultation emails for testing."""
        return [
            {
                "id": "test_email_001",
                "subject": "GLG Test Consultation - AI/ML Expertise",
                "sender": "noreply@glgroup.com",
                "sender_email": "noreply@glgroup.com",
                "date": "2025-11-30T10:00:00Z",
                "platform": "glg",
                "email_type": "consultation_invitation",
                "bodyText": "We have a consultation opportunity about AI/ML...",
                "consultation_details": {
                    "platform": "glg",
                    "project_id": "test_project_123",
                    "skills_required": ["AI/ML", "Cloud Computing"],
                    "budget": "$500/hour",
                    "project_url": "https://members.glgresearch.com/accept/test_project_123"
                }
            },
            {
                "id": "test_email_002",
                "subject": "GLG Test Consultation - Mobile App Security",
                "sender": "noreply@glgroup.com",
                "sender_email": "noreply@glgroup.com",
                "date": "2025-11-30T11:00:00Z",
                "platform": "glg",
                "email_type": "consultation_invitation",
                "bodyText": "Mobile application security consultation...",
                "consultation_details": {
                    "platform": "glg",
                    "project_id": "test_project_124",
                    "skills_required": ["Mobile Security", "iOS"],
                    "budget": "$400/hour",
                    "project_url": "https://members.glgresearch.com/accept/test_project_124"
                }
            }
        ]

    @pytest.fixture
    def mock_agent_context_full(self, mock_consultation_emails):
        """Create a comprehensive mock agent context for workflow testing."""
        from src.memory.store import MemoryStore
        from src.analytics.metrics import MetricsTracker
        from src.analytics.reporter import Reporter
        from src.profile.aggregator import ProfileAggregator
        from src.email.processor import EmailProcessor
        from src.platforms.registry import PlatformRegistry

        # Create mocks for all components
        memory_store = MagicMock(spec=MemoryStore)
        metrics = MagicMock(spec=MetricsTracker)
        reporter = MagicMock(spec=Reporter)
        profile_aggregator = MagicMock(spec=ProfileAggregator)
        email_processor = MagicMock(spec=EmailProcessor)
        platform_registry = MagicMock(spec=PlatformRegistry)

        # Configure email processor mock
        email_processor.list_recent_emails = AsyncMock(return_value=mock_consultation_emails)

        # Configure Gmail client mock
        gmail_client = MagicMock()
        gmail_client.archive_email = MagicMock()
        email_processor.gmail = gmail_client

        # Configure metrics mock
        metrics.record_email_archived = MagicMock()
        metrics.get_summary = MagicMock(return_value={
            "total_consultations": 2,
            "total_acceptances": 1,
            "total_rejections": 1,
            "emails_archived": 2,
        })

        # Configure memory store mock
        memory_store.record_consultation = MagicMock()
        memory_store.is_processed = MagicMock(return_value=False)

        # Configure reporter mock
        reporter.generate_daily_report = AsyncMock(return_value="Test report generated")

        # Configure profile aggregator mock
        profile_aggregator.aggregate = AsyncMock(return_value={
            "name": "Test User",
            "expertise": ["AI/ML", "Cloud Computing"],
            "rate_range": "$500-1000/hour"
        })

        context = AgentContext(
            memory_store=memory_store,
            metrics=metrics,
            reporter=reporter,
            profile_aggregator=profile_aggregator,
            email_processor=email_processor,
            platform_registry=platform_registry,
            correlation_id="integration_test_123",
        )

        return context

    @pytest.mark.asyncio
    async def test_complete_accept_workflow_with_archiving(self, mock_agent_context_full):
        """Test complete accept workflow: fetch → decide → submit → record → archive."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context_full

        # Step 1: Fetch recent emails
        emails_result = await list_recent_consultation_emails({"days_back": 7})
        emails_data = json.loads(emails_result["content"][0]["text"])
        assert len(emails_data) == 2

        # Step 2: Process first email (AI/ML - should be accepted)
        ai_email = emails_data[0]
        email_id = ai_email["id"]

        # Step 3: Record consultation decision (accept)
        decision_args = {
            "email_id": email_id,
            "platform": "glg",
            "subject": ai_email["subject"],
            "decision": "accept",
            "reasoning": "Strong fit for AI/ML expertise and $500/hour rate",
            "project_id": "test_project_123",
            "submission_details": {"message": "Successfully submitted application"}
        }
        decision_result = await record_consultation_decision(decision_args)
        assert "is_error" not in decision_result

        # Step 4: Archive the processed email
        archive_args = {"email_id": email_id}
        archive_result = await archive_email(archive_args)

        # Verify archiving was successful
        assert "is_error" not in archive_result
        assert f"Successfully archived email {email_id}" in archive_result["content"][0]["text"]

        # Verify Gmail client was called
        mock_agent_context_full.email_processor.gmail.archive_email.assert_called_with(email_id)

        # Verify metrics were updated
        mock_agent_context_full.metrics.record_email_archived.assert_called()

        # Verify consultation was recorded
        mock_agent_context_full.memory_store.record_consultation.assert_called()

    @pytest.mark.asyncio
    async def test_complete_decline_workflow_with_archiving(self, mock_agent_context_full):
        """Test complete decline workflow: fetch → decide → reply → record → archive."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context_full

        # Step 1: Fetch recent emails
        emails_result = await list_recent_consultation_emails({"days_back": 7})
        emails_data = json.loads(emails_result["content"][0]["text"])

        # Step 2: Process second email (Mobile Security - should be declined)
        mobile_email = emails_data[1]
        email_id = mobile_email["id"]

        # Step 3: Record consultation decision (decline)
        decision_args = {
            "email_id": email_id,
            "platform": "glg",
            "subject": mobile_email["subject"],
            "decision": "decline",
            "reasoning": "Outside expertise area - mobile security not my domain",
            "project_id": "test_project_124",
            "submission_details": {"message": "Declined - skills mismatch"}
        }
        decision_result = await record_consultation_decision(decision_args)
        assert "is_error" not in decision_result

        # Step 4: Archive the processed email
        archive_args = {"email_id": email_id}
        archive_result = await archive_email(archive_args)

        # Verify archiving was successful
        assert "is_error" not in archive_result
        assert f"Successfully archived email {email_id}" in archive_result["content"][0]["text"]

        # Verify workflow completed
        mock_agent_context_full.email_processor.gmail.archive_email.assert_called_with(email_id)
        mock_agent_context_full.metrics.record_email_archived.assert_called()

    @pytest.mark.asyncio
    async def test_batch_processing_with_archiving(self, mock_agent_context_full):
        """Test batch processing of multiple emails with archiving."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context_full

        # Fetch all emails
        emails_result = await list_recent_consultation_emails({"days_back": 7})
        emails_data = json.loads(emails_result["content"][0]["text"])

        archived_count = 0
        processed_emails = []

        # Process each email
        for email_data in emails_data:
            email_id = email_data["id"]

            # Simulate decision making (accept AI/ML, decline mobile security)
            if "AI/ML" in email_data["subject"]:
                decision = "accept"
                reasoning = "Strong AI/ML expertise match"
                submission_details = {"message": "Application submitted successfully"}
            else:
                decision = "decline"
                reasoning = "Outside expertise area"
                submission_details = {"message": "Declined - skills mismatch"}

            # Record decision
            decision_args = {
                "email_id": email_id,
                "platform": email_data["platform"],
                "subject": email_data["subject"],
                "decision": decision,
                "reasoning": reasoning,
                "project_id": email_data["consultation_details"]["project_id"],
                "submission_details": submission_details
            }
            await record_consultation_decision(decision_args)

            # Archive email
            archive_result = await archive_email({"email_id": email_id})
            if "is_error" not in archive_result:
                archived_count += 1
                processed_emails.append(email_id)

        # Verify all emails were processed and archived
        assert archived_count == 2
        assert len(processed_emails) == 2

        # Verify Gmail client was called for each email
        assert mock_agent_context_full.email_processor.gmail.archive_email.call_count == 2

        # Verify metrics were updated for each archived email
        assert mock_agent_context_full.metrics.record_email_archived.call_count == 2

    @pytest.mark.asyncio
    async def test_workflow_with_archiving_failure(self, mock_agent_context_full):
        """Test workflow when archiving fails but other steps succeed."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context_full

        # Configure Gmail client to fail on archiving
        mock_agent_context_full.email_processor.gmail.archive_email.side_effect = Exception("Gmail API error")

        # Fetch emails
        emails_result = await list_recent_consultation_emails({"days_back": 7})
        emails_data = json.loads(emails_result["content"][0]["text"])
        email_id = emails_data[0]["id"]

        # Record decision successfully
        decision_args = {
            "email_id": email_id,
            "platform": "glg",
            "subject": emails_data[0]["subject"],
            "decision": "accept",
            "reasoning": "Good fit",
            "project_id": "test_project_123",
            "submission_details": {"message": "Submitted"}
        }
        decision_result = await record_consultation_decision(decision_args)
        assert "is_error" not in decision_result

        # Try to archive - should fail gracefully
        archive_result = await archive_email({"email_id": email_id})

        # Verify archiving failed but returned proper error
        assert archive_result["is_error"] is True
        assert "Gmail API error" in archive_result["content"][0]["text"]

        # Verify decision was still recorded (workflow can continue)
        mock_agent_context_full.memory_store.record_consultation.assert_called()

        # Verify metrics were NOT updated due to archiving failure
        mock_agent_context_full.metrics.record_email_archived.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_report_after_archiving(self, mock_agent_context_full):
        """Test that finalize_run_and_report works after archiving operations."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context_full

        # Process and archive emails
        emails_result = await list_recent_consultation_emails({"days_back": 7})
        emails_data = json.loads(emails_result["content"][0]["text"])

        for email_data in emails_data:
            email_id = email_data["id"]

            # Record decision
            decision_args = {
                "email_id": email_id,
                "platform": email_data["platform"],
                "subject": email_data["subject"],
                "decision": "accept",
                "reasoning": "Test reasoning",
                "project_id": email_data["consultation_details"]["project_id"],
                "submission_details": {"message": "Test submission"}
            }
            await record_consultation_decision(decision_args)

            # Archive email
            await archive_email({"email_id": email_id})

        # Finalize report
        report_result = await finalize_run_and_report({})

        # Verify report was generated
        assert "is_error" not in report_result
        report_data = json.loads(report_result["content"][0]["text"])
        assert "report" in report_data
        assert "metrics" in report_data

        # Verify metrics include archiving information
        metrics = report_data["metrics"]
        assert "emails_archived" in metrics
        assert metrics["emails_archived"] == 2  # Based on mock configuration


class TestAgentArchivingErrorRecovery:
    """Test error recovery scenarios in archiving workflow."""

    @pytest.fixture
    def mock_context_with_partial_failures(self):
        """Mock context that simulates partial failures in archiving."""
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "error_recovery_test"

        # Gmail client that fails intermittently
        gmail_client = MagicMock()
        call_count = [0]  # Use list to make it mutable in closure

        def archive_side_effect(email_id):
            call_count[0] += 1
            if call_count[0] % 2 == 0:  # Fail every second call
                raise Exception(f"Intermittent failure for {email_id}")
            return None  # Success

        gmail_client.archive_email.side_effect = archive_side_effect
        mock_ctx.email_processor.gmail = gmail_client
        mock_ctx.metrics.record_email_archived = MagicMock()

        return mock_ctx

    @pytest.mark.asyncio
    async def test_partial_archiving_failures_in_batch(self, mock_context_with_partial_failures):
        """Test handling of partial failures when archiving multiple emails."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_context_with_partial_failures

        # Test multiple email IDs
        email_ids = ["email_001", "email_002", "email_003", "email_004"]

        success_count = 0
        failure_count = 0

        for email_id in email_ids:
            result = await archive_email({"email_id": email_id})

            if "is_error" in result and result["is_error"]:
                failure_count += 1
            else:
                success_count += 1

        # Based on the mock, every second call fails
        assert success_count == 2
        assert failure_count == 2

        # Verify metrics only updated for successful archives
        assert mock_context_with_partial_failures.metrics.record_email_archived.call_count == 2

    @pytest.mark.asyncio
    async def test_continue_workflow_after_archive_failure(self, mock_context_with_partial_failures):
        """Test that workflow continues even if individual archive operations fail."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_context_with_partial_failures

        # Mock other workflow components
        mock_context_with_partial_failures.memory_store.record_consultation = MagicMock()

        # Simulate workflow with archiving failure
        email_id = "failing_email_001"

        # Record decision first (this should succeed)
        decision_args = {
            "email_id": email_id,
            "platform": "glg",
            "subject": "Test Subject",
            "decision": "accept",
            "reasoning": "Good fit",
            "project_id": "test_project",
            "submission_details": {"message": "Success"}
        }
        decision_result = await record_consultation_decision(decision_args)
        assert "is_error" not in decision_result

        # Try to archive (this will fail based on mock)
        archive_result = await archive_email({"email_id": email_id})
        assert archive_result["is_error"] is True

        # Verify that decision was still recorded despite archiving failure
        mock_context_with_partial_failures.memory_store.record_consultation.assert_called()

        # This demonstrates that the workflow can continue even with archiving failures
        # The agent should log the error but not stop processing other emails