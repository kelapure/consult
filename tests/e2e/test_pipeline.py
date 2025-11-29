"""
Full pipeline smoke test (Phase 3.21).

This test simulates the accept workflow from email parsing through metrics,
memory storage, and reporting without invoking the Claude Agent SDK.
"""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.analytics.metrics import MetricsTracker
from src.analytics.reporter import Reporter
from src.memory.store import MemoryStore
from src.platforms.registry import PlatformRegistry

load_dotenv()


@pytest.mark.asyncio
async def test_full_pipeline_accept_flow(tmp_path):
    """
    Simulate: email → application prep → submission result → memory store → report.
    """
    memory_store = MemoryStore()
    metrics = MetricsTracker()
    reporter = Reporter(memory_store, metrics)
    reporter.reports_dir = tmp_path / "reports"
    reporter.reports_dir.mkdir(exist_ok=True)

    consultation = {
        "email_id": "glg-email-001",
        "platform": "GLG",
        "project_id": "GLG-ACCT-1",
        "subject": "GLG | AI Transformation Advisor",
        "project_url": "https://client.glginsights.com/project/demo",
        "rate": 450,
    }

    profile_context = {
        "summary": "15 years leading global cloud transformations for Fortune 100 banks.",
        "industries": ["technology", "financial services"],
    }

    registry = PlatformRegistry()
    platform = registry.get_platform("glg")
    form_payload = await platform.prepare_application(
        {**consultation, "profile_context": profile_context}
    )

    # Stub submission result (Computer Use already covered by integration tests)
    submission_details = {
        "success": True,
        "method": "claude",
        "actions": [{"action": "type", "text": "demo"}],
        "form_data": form_payload,
    }

    metrics.record_email_processed()
    metrics.record_application("GLG")
    metrics.record_consultation_detail(
        email_id=consultation["email_id"],
        subject=consultation["subject"],
        platform=consultation["platform"],
        decision="accept",
        reasoning="Deep cloud + AI fit",
        actions_taken=["prepared_application", "pending_submission"],
    )

    memory_store.record_consultation(
        email_id=consultation["email_id"],
        platform=consultation["platform"],
        subject=consultation["subject"],
        decision="accept",
        reasoning="Strong expertise alignment",
        project_id=consultation["project_id"],
        submission_details=submission_details,
    )

    run_id = "pipeline-smoke"
    metrics_summary = metrics.get_summary()
    memory_store.save_run_metrics(run_id, metrics_summary)

    report = await reporter.generate_daily_report(send_email=False)

    saved = memory_store.get_consultation(consultation["email_id"])
    assert saved is not None
    assert saved["decision"] == "accept"
    assert metrics_summary["total_applications"] == 1
    assert report["summary"]["emails_processed"] == 1

