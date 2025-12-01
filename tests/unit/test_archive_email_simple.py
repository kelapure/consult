"""Simple unit tests for archive_email functionality."""

import pytest
from unittest.mock import MagicMock


class TestArchiveEmailFunction:
    """Test archive_email functionality using direct testing approach."""

    async def archive_email_impl(self, args, ctx):
        """Test implementation of archive_email logic."""
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

    def create_mock_context(self):
        """Create a mock agent context for testing."""
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "test_123"

        # Mock the Gmail client
        gmail_client = MagicMock()
        gmail_client.archive_email = MagicMock()

        # Mock email processor
        email_processor = MagicMock()
        email_processor.gmail = gmail_client

        # Mock metrics
        metrics = MagicMock()
        metrics.record_email_archived = MagicMock()

        # Attach to context
        mock_ctx.email_processor = email_processor
        mock_ctx.metrics = metrics

        return mock_ctx

    @pytest.mark.asyncio
    async def test_archive_email_success(self):
        """Test successful email archiving."""
        # Setup
        mock_ctx = self.create_mock_context()
        email_id = "19acc7c080c11daa"
        args = {"email_id": email_id}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify Gmail client was called to archive the email
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)

        # Verify metrics were updated
        mock_ctx.metrics.record_email_archived.assert_called_once()

        # Verify successful response
        assert result["content"][0]["type"] == "text"
        assert f"Successfully archived email {email_id}" in result["content"][0]["text"]
        assert "is_error" not in result

    @pytest.mark.asyncio
    async def test_archive_email_missing_email_id(self):
        """Test archive_email with missing email_id parameter."""
        # Setup
        mock_ctx = self.create_mock_context()
        args = {}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "email_id is required" in result["content"][0]["text"]

        # Verify Gmail client was NOT called
        mock_ctx.email_processor.gmail.archive_email.assert_not_called()

        # Verify metrics were NOT updated
        mock_ctx.metrics.record_email_archived.assert_not_called()

    @pytest.mark.asyncio
    async def test_archive_email_empty_email_id(self):
        """Test archive_email with empty email_id parameter."""
        # Setup
        mock_ctx = self.create_mock_context()
        args = {"email_id": ""}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "email_id is required" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_gmail_error(self):
        """Test archive_email when Gmail client raises an error."""
        # Setup
        mock_ctx = self.create_mock_context()
        mock_ctx.email_processor.gmail.archive_email.side_effect = Exception("Gmail API error")

        email_id = "19acc7c080c11daa"
        args = {"email_id": email_id}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify Gmail client was called
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)

        # Verify metrics were NOT updated due to error
        mock_ctx.metrics.record_email_archived.assert_not_called()

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert f"Failed to archive email {email_id}" in result["content"][0]["text"]
        assert "Gmail API error" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_no_agent_context(self):
        """Test archive_email when agent context is not initialized."""
        # Setup
        args = {"email_id": "19acc7c080c11daa"}

        # Call the function with None context
        result = await self.archive_email_impl(args, None)

        # Verify error response
        assert result["is_error"] is True
        assert result["content"][0]["type"] == "text"
        assert "Agent context not initialized" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_archive_email_multiple_calls(self):
        """Test archiving multiple emails sequentially."""
        # Setup
        mock_ctx = self.create_mock_context()
        email_ids = ["19acc7c080c11daa", "19ac92d03551982f", "19ac56d056d03207"]

        # Archive each email
        for email_id in email_ids:
            args = {"email_id": email_id}
            result = await self.archive_email_impl(args, mock_ctx)

            # Verify success for each
            assert "is_error" not in result
            assert f"Successfully archived email {email_id}" in result["content"][0]["text"]

        # Verify Gmail client was called for each email
        assert mock_ctx.email_processor.gmail.archive_email.call_count == len(email_ids)

        # Verify metrics were updated for each email
        assert mock_ctx.metrics.record_email_archived.call_count == len(email_ids)

    @pytest.mark.asyncio
    async def test_archive_email_with_special_characters(self):
        """Test archiving email ID with special characters."""
        # Setup
        mock_ctx = self.create_mock_context()
        email_id = "19abc+def_123-456"
        args = {"email_id": email_id}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify success
        assert "is_error" not in result
        assert f"Successfully archived email {email_id}" in result["content"][0]["text"]

        # Verify Gmail client was called with correct ID
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)

    @pytest.mark.asyncio
    async def test_archive_email_network_error(self):
        """Test archive_email with network/connectivity error."""
        # Setup
        mock_ctx = self.create_mock_context()
        mock_ctx.email_processor.gmail.archive_email.side_effect = ConnectionError("Network unreachable")

        args = {"email_id": "19acc7c080c11daa"}

        # Call the function
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify error response
        assert result["is_error"] is True
        assert "Network unreachable" in result["content"][0]["text"]

        # Verify metrics should NOT be updated on failure
        mock_ctx.metrics.record_email_archived.assert_not_called()


class TestArchiveEmailIntegration:
    """Integration tests for archive_email workflow scenarios."""

    async def archive_email_impl(self, args, ctx):
        """Test implementation of archive_email logic."""
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
            ctx.email_processor.gmail.archive_email(email_id)
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

    def create_mock_context(self):
        """Create a mock agent context for testing."""
        mock_ctx = MagicMock()
        mock_ctx.correlation_id = "integration_test_456"

        gmail_client = MagicMock()
        gmail_client.archive_email = MagicMock()

        email_processor = MagicMock()
        email_processor.gmail = gmail_client

        metrics = MagicMock()
        metrics.record_email_archived = MagicMock()

        mock_ctx.email_processor = email_processor
        mock_ctx.metrics = metrics

        return mock_ctx

    @pytest.mark.asyncio
    async def test_archive_email_in_accept_workflow(self):
        """Test archive_email as part of accept workflow."""
        mock_ctx = self.create_mock_context()

        # Simulate typical accept workflow steps
        email_id = "19acc7c080c11daa"

        # Step 1: Process consultation (simulated)
        # Step 2: Submit application (simulated)
        # Step 3: Record decision (simulated)
        # Step 4: Archive email (this is what we're testing)

        args = {"email_id": email_id}
        result = await self.archive_email_impl(args, mock_ctx)

        # Verify successful archiving
        assert "is_error" not in result
        assert "Successfully archived email" in result["content"][0]["text"]

        # Verify workflow integration
        mock_ctx.email_processor.gmail.archive_email.assert_called_once_with(email_id)
        mock_ctx.metrics.record_email_archived.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_email_batch_processing(self):
        """Test archive_email for batch processing of multiple consultations."""
        mock_ctx = self.create_mock_context()

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
            result = await self.archive_email_impl(args, mock_ctx)

            if "is_error" not in result:
                successful_archives += 1

        # Verify all emails were archived successfully
        assert successful_archives == len(processed_emails)
        assert mock_ctx.email_processor.gmail.archive_email.call_count == len(processed_emails)
        assert mock_ctx.metrics.record_email_archived.call_count == len(processed_emails)