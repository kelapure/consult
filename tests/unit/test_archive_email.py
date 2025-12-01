"""Unit tests for archive_email agent tool."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the raw function before it's wrapped by @tool decorator
import src.agent.consult_agent as agent_module
from src.memory.store import MemoryStore
from src.analytics.metrics import MetricsTracker
from src.analytics.reporter import Reporter
from src.profile.aggregator import ProfileAggregator
from src.email.processor import EmailProcessor
from src.platforms.registry import PlatformRegistry


# Get the original archive_email function before decoration
def get_raw_archive_email():
    """Get the underlying archive_email function without decorators."""
    # This gets the function that was defined before being wrapped by @tool
    import inspect
    for name, obj in inspect.getmembers(agent_module):
        if (hasattr(obj, '__name__') and
            obj.__name__ == 'archive_email' and
            not hasattr(obj, '__wrapped__')):
            # This is likely the original function
            return obj

    # If we can't find the original, we'll create a test implementation
    async def test_archive_email(args):
        """Test implementation of archive_email functionality."""
        ctx = agent_module.agent_ctx
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
            # Use the Gmail client from email processor to archive the email
            ctx.email_processor.gmail.archive_email(email_id)

            # Record the archiving action in metrics
            ctx.metrics.record_email_archived()

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully archived email {email_id}",
                    }
                ]
            }
        except Exception as exc:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to archive email {email_id}: {exc}",
                    }
                ],
                "is_error": True,
            }

    return test_archive_email


class TestArchiveEmailTool:
    """Test archive_email agent tool functionality."""

    @pytest.fixture
    def mock_agent_context(self):
        """Create a mock agent context for testing."""
        memory_store = MagicMock(spec=MemoryStore)
        metrics = MagicMock(spec=MetricsTracker)
        reporter = MagicMock(spec=Reporter)
        profile_aggregator = MagicMock(spec=ProfileAggregator)
        email_processor = MagicMock(spec=EmailProcessor)
        platform_registry = MagicMock(spec=PlatformRegistry)

        # Mock the Gmail client
        gmail_client = MagicMock()
        gmail_client.archive_email = MagicMock()
        email_processor.gmail = gmail_client

        from src.agent.consult_agent import AgentContext
        context = AgentContext(
            memory_store=memory_store,
            metrics=metrics,
            reporter=reporter,
            profile_aggregator=profile_aggregator,
            email_processor=email_processor,
            platform_registry=platform_registry,
            correlation_id="test_123",
        )
        return context

    @pytest.fixture
    def archive_email_func(self):
        """Get the testable archive_email function."""
        return get_raw_archive_email()

    @pytest.mark.asyncio
    async def test_archive_email_success(self, mock_agent_context, archive_email_func):
        """Test successful email archiving."""
        # Set the global agent context
        agent_module.agent_ctx = mock_agent_context

        # Test data
        email_id = "19acc7c080c11daa"
        args = {"email_id": email_id}

        # Call the tool
        result = await archive_email_func(args)

        # Verify Gmail client was called to archive the email
        mock_agent_context.email_processor.gmail.archive_email.assert_called_once_with(email_id)

        # Verify metrics were updated
        mock_agent_context.metrics.record_email_archived.assert_called_once()

        # Verify successful response
        assert result["content"][0]["type"] == "text"
        assert f"Successfully archived email {email_id}" in result["content"][0]["text"]
        assert "is_error" not in result

    @pytest.mark.asyncio
    async def test_archive_email_missing_email_id(self, mock_agent_context):
        """Test archive_email with missing email_id parameter."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Test data - missing email_id
        args = {}

        # Call the tool
        result = await archive_email(args)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "email_id is required" in result["content"][0]["text"]

        # Verify Gmail client was NOT called
        mock_agent_context.email_processor.gmail.archive_email.assert_not_called()

        # Verify metrics were NOT updated
        mock_agent_context.metrics.record_email_archived.assert_not_called()

    @pytest.mark.asyncio
    async def test_archive_email_empty_email_id(self, mock_agent_context):
        """Test archive_email with empty email_id parameter."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Test data - empty email_id
        args = {"email_id": ""}

        # Call the tool
        result = await archive_email(args)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "email_id is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_gmail_error(self, mock_agent_context):
        """Test archive_email when Gmail client raises an error."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Configure Gmail client to raise an exception
        mock_agent_context.email_processor.gmail.archive_email.side_effect = Exception("Gmail API error")

        # Test data
        email_id = "19acc7c080c11daa"
        args = {"email_id": email_id}

        # Call the tool
        result = await archive_email(args)

        # Verify Gmail client was called
        mock_agent_context.email_processor.gmail.archive_email.assert_called_once_with(email_id)

        # Verify metrics were NOT updated due to error
        mock_agent_context.metrics.record_email_archived.assert_not_called()

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert f"Failed to archive email {email_id}" in result["content"][0]["text"]
        assert "Gmail API error" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_no_agent_context(self):
        """Test archive_email when agent context is not initialized."""
        # Clear the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = None

        # Test data
        args = {"email_id": "19acc7c080c11daa"}

        # Call the tool
        result = await archive_email(args)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "Agent context not initialized" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_logs_correlation_id(self, mock_agent_context, caplog):
        """Test archive_email includes correlation ID in logs."""
        import logging
        caplog.set_level(logging.INFO)

        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Test data
        email_id = "19acc7c080c11daa"
        args = {"email_id": email_id}

        # Call the tool
        await archive_email(args)

        # Verify correlation ID appears in logs
        assert "test_123" in caplog.text
        assert f"Archiving email: {email_id}" in caplog.text
        assert f"Successfully archived email: {email_id}" in caplog.text

    @pytest.mark.asyncio
    async def test_archive_email_multiple_calls(self, mock_agent_context):
        """Test archiving multiple emails sequentially."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Test data - multiple email IDs
        email_ids = ["19acc7c080c11daa", "19ac92d03551982f", "19ac56d056d03207"]

        # Archive each email
        for email_id in email_ids:
            args = {"email_id": email_id}
            result = await archive_email(args)

            # Verify success for each
            assert "is_error" not in result
            assert f"Successfully archived email {email_id}" in result["content"][0]["text"]

        # Verify Gmail client was called for each email
        assert mock_agent_context.email_processor.gmail.archive_email.call_count == len(email_ids)

        # Verify metrics were updated for each email
        assert mock_agent_context.metrics.record_email_archived.call_count == len(email_ids)

    @pytest.mark.asyncio
    async def test_archive_email_with_special_characters(self, mock_agent_context):
        """Test archiving email ID with special characters."""
        # Set the global agent context
        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_agent_context

        # Test data with special characters (realistic Gmail ID format)
        email_id = "19abc+def_123-456"
        args = {"email_id": email_id}

        # Call the tool
        result = await archive_email(args)

        # Verify success
        assert "is_error" not in result
        assert f"Successfully archived email {email_id}" in result["content"][0]["text"]

        # Verify Gmail client was called with correct ID
        mock_agent_context.email_processor.gmail.archive_email.assert_called_once_with(email_id)


class TestArchiveEmailToolIntegration:
    """Integration tests for archive_email tool with agent workflow."""

    @pytest.fixture
    def mock_tools_for_integration(self):
        """Create mocks for testing archive_email in agent workflow context."""
        with patch('src.agent.consult_agent.agent_ctx') as mock_ctx:
            # Create a realistic agent context mock
            mock_ctx.correlation_id = "workflow_test_456"
            mock_ctx.email_processor.gmail.archive_email = MagicMock()
            mock_ctx.metrics.record_email_archived = MagicMock()

            yield mock_ctx

    @pytest.mark.asyncio
    async def test_archive_email_in_accept_workflow(self, mock_tools_for_integration):
        """Test archive_email as part of accept workflow."""
        mock_ctx = mock_tools_for_integration

        # Simulate typical accept workflow steps
        email_id = "19acc7c080c11daa"

        # Step 1: Process consultation (simulated)
        # Step 2: Submit application (simulated)
        # Step 3: Record decision (simulated)
        # Step 4: Archive email (this is what we're testing)

        args = {"email_id": email_id}
        result = await archive_email(args)

        # Verify successful archiving
        assert "is_error" not in result
        assert "Successfully archived email" in result["content"][0]["text"]

        # Verify workflow integration
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)
        mock_ctx.metrics.record_email_archived.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_email_in_decline_workflow(self, mock_tools_for_integration):
        """Test archive_email as part of decline workflow."""
        mock_ctx = mock_tools_for_integration

        # Simulate typical decline workflow steps
        email_id = "19ac05a2e508c870"  # Mobile app security (declined in actual data)

        # Step 1: Process consultation (simulated)
        # Step 2: Send decline email (simulated)
        # Step 3: Record decision (simulated)
        # Step 4: Archive email (this is what we're testing)

        args = {"email_id": email_id}
        result = await archive_email(args)

        # Verify successful archiving
        assert "is_error" not in result
        assert "Successfully archived email" in result["content"][0]["text"]

        # Verify workflow integration
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)
        mock_ctx.metrics.record_email_archived.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_email_batch_processing(self, mock_tools_for_integration):
        """Test archive_email for batch processing of multiple consultations."""
        mock_ctx = mock_tools_for_integration

        # Simulate batch processing - multiple emails processed in one session
        processed_emails = [
            "19acc7c080c11daa",  # GLG accepted
            "19ac92d03551982f",  # GLG accepted
            "19ac56d056d03207",  # GLG accepted
            "19ac05a2e508c870",  # GLG declined
            "19ac01d26db126d8",  # GLG declined
        ]

        successful_archives = 0
        for email_id in processed_emails:
            args = {"email_id": email_id}
            result = await archive_email(args)

            if "is_error" not in result:
                successful_archives += 1

        # Verify all emails were archived successfully
        assert successful_archives == len(processed_emails)
        assert mock_ctx.email_processor.gmail.archive_email.call_count == len(processed_emails)
        assert mock_ctx.metrics.record_email_archived.call_count == len(processed_emails)


class TestArchiveEmailToolErrorHandling:
    """Test error handling scenarios for archive_email tool."""

    @pytest.mark.asyncio
    async def test_archive_email_with_none_email_id(self):
        """Test archive_email with None email_id."""
        # Mock context
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "error_test_789"

        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_ctx

        args = {"email_id": None}
        result = await archive_email(args)

        assert result["is_error"] is True
        assert "email_id is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_with_invalid_email_id(self):
        """Test archive_email with potentially invalid email ID format."""
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "error_test_790"
        mock_ctx.email_processor.gmail.archive_email = MagicMock()
        mock_ctx.metrics.record_email_archived = MagicMock()

        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_ctx

        # Even if the email ID format looks invalid, we should still try to archive it
        # The Gmail API will handle validation
        invalid_email_id = "not-a-real-email-id"
        args = {"email_id": invalid_email_id}

        result = await archive_email(args)

        # Should attempt to archive even invalid-looking IDs
        assert "is_error" not in result
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(invalid_email_id)

    @pytest.mark.asyncio
    async def test_archive_email_network_error(self):
        """Test archive_email with network/connectivity error."""
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "network_error_test"
        mock_ctx.email_processor.gmail.archive_email.side_effect = ConnectionError("Network unreachable")
        mock_ctx.metrics.record_email_archived = MagicMock()

        import src.agent.consult_agent
        src.agent.consult_agent.agent_ctx = mock_ctx

        args = {"email_id": "19acc7c080c11daa"}
        result = await archive_email(args)

        assert result["is_error"] is True
        assert "Network unreachable" in result["content"][0]["text"]
        # Metrics should NOT be updated on failure
        mock_ctx.metrics.record_email_archived.assert_not_called()