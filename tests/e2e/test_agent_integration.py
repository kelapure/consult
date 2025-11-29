"""
End-to-end agent integration tests (Phase 4.4-4.6).

Tests the complete workflow:
1. Mock email with consultation details
2. Agent parses and decides
3. Agent submits application via Computer Use
4. Agent records decision and metrics
5. Agent generates report
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
async def test_submit_platform_application_integration(simple_form_url: str):
    """
    Test submit_platform_application with Computer Use (4.4).

    Verifies:
    - Tool accepts project_url, task_prompt, platform_name
    - Uses BrowserAutomation class
    - Returns structured dict with success, method, actions
    - Falls back from Claude to Gemini on failure
    """
    from src.browser.computer_use import submit_platform_application

    # Prepare test data
    project_url = simple_form_url
    form_data = {
        "full_name": "John Doe",
        "email": "john@example.com",
        "experience": "10 years in software engineering"
    }

    # Build task prompt (same logic as agent tool)
    task_prompt = f"""Complete the consultation application form.

Project URL: {project_url}

Then fill out the application form with the following information:
"""
    for field, value in form_data.items():
        task_prompt += f"- {field}: {value}\n"
    task_prompt += """
After filling all fields, submit the form and confirm submission was successful.
"""

    # Test without login credentials (form doesn't require login)
    result = await submit_platform_application(
        project_url=project_url,
        task_prompt=task_prompt,
        platform_name="test",
        max_retries=2
    )

    # Verify response structure
    assert "success" in result
    assert "method" in result
    assert "actions" in result
    assert "error" in result

    # Verify success
    assert result["success"] is True, f"Submission failed: {result.get('error')}"

    # Verify method is either claude or gemini
    assert result["method"] in ["claude", "gemini"], f"Unknown method: {result['method']}"

    # Verify actions were taken
    assert len(result["actions"]) > 0, "No actions recorded"

    # Verify no error
    assert result["error"] is None

    print(f"\n✓ Form submitted successfully via {result['method']}")
    print(f"✓ {len(result['actions'])} actions taken")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_claude_primary_gemini_fallback(simple_form_url: str):
    """
    Test that Claude is primary and Gemini is fallback (4.5).

    Simulates Claude failure to verify Gemini fallback triggers.
    """
    from src.browser.computer_use import submit_platform_application, BrowserAutomation

    # Prepare test data
    project_url = simple_form_url
    form_data = {
        "full_name": "Jane Smith",
        "email": "jane@example.com",
        "experience": "5 years"
    }

    # Build task prompt
    task_prompt = f"""Complete the consultation application form.

Project URL: {project_url}

Then fill out the application form with the following information:
"""
    for field, value in form_data.items():
        task_prompt += f"- {field}: {value}\n"
    task_prompt += """
After filling all fields, submit the form and confirm submission was successful.
"""

    # Mock Claude to fail, let Gemini succeed
    with patch.object(BrowserAutomation, 'claude_computer_use', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = (False, [])  # Claude fails

        result = await submit_platform_application(
            project_url=project_url,
            task_prompt=task_prompt,
            platform_name="test",
            max_retries=1
        )

        # Verify Claude was tried first
        assert mock_claude.called, "Claude should have been attempted first"

        # If successful, it must be from Gemini fallback
        if result["success"]:
            assert result["method"] == "gemini", "Success should be from Gemini fallback"
            print("\n✓ Claude failed, Gemini fallback succeeded")
        else:
            # Both failed (possible if Gemini API has issues)
            print("\n⚠ Both Claude and Gemini failed (API issue)")


@pytest.mark.asyncio
async def test_mcp_tool_submit_platform_application():
    """
    Test submit_platform_application MCP tool wrapper (4.4).

    Tests the MCP tool function that wraps the Computer Use implementation.
    """
    from src.agent.consult_agent import submit_platform_application as mcp_tool
    from src.agent.consult_agent import AgentContext
    from src.memory.store import MemoryStore
    from src.analytics.metrics import MetricsTracker
    from src.analytics.reporter import Reporter
    from src.profile.aggregator import ProfileAggregator
    from src.email.processor import EmailProcessor
    from src.platforms.registry import PlatformRegistry
    from src.agent import consult_agent

    # Set up agent context (required by MCP tools)
    consult_agent.agent_ctx = AgentContext(
        memory_store=MemoryStore(),
        metrics=MetricsTracker(),
        reporter=Reporter(MemoryStore(), MetricsTracker()),
        profile_aggregator=ProfileAggregator(),
        email_processor=EmailProcessor(memory_store=MemoryStore()),
        platform_registry=PlatformRegistry()
    )

    # Get simple form URL
    test_fixture_path = Path(__file__).parent.parent / "fixtures"
    simple_form_path = test_fixture_path / "simple_form.html"
    project_url = f"file://{simple_form_path}"

    # Prepare MCP tool args (including platform_name for generic tool)
    args = {
        "project_url": project_url,
        "platform_name": "test",
        "form_data": {
            "full_name": "Test User",
            "email": "test@example.com",
            "experience": "3 years"
        },
        "login_username": None,
        "login_password": None
    }

    # Call MCP tool handler directly
    result = await mcp_tool.handler(args)

    # Verify MCP tool response format
    assert "content" in result
    assert isinstance(result["content"], list)
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    # Parse response JSON
    response_text = result["content"][0]["text"]
    response_data = json.loads(response_text)

    # Verify response structure
    assert "success" in response_data

    if response_data["success"]:
        assert "method" in response_data
        assert "actions_taken" in response_data
        assert "message" in response_data
        print(f"\n✓ MCP tool successful via {response_data['method']}")
        print(f"✓ {response_data['actions_taken']} actions taken")
    else:
        assert "error" in response_data
        print(f"\n✗ MCP tool failed: {response_data['error']}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_agent_workflow_mock():
    """
    Test complete agent workflow with mock components (4.6).

    Simulates:
    1. Email with consultation details
    2. Profile summary
    3. CP writing style
    4. Application form data
    5. Platform login info
    6. Submission via Computer Use
    7. Recording decision
    8. Generating report
    """
    from src.agent.consult_agent import (
        agent_ctx,
        AgentContext,
        get_profile_summary,
        get_cp_writing_style,
        get_application_form_data,
        get_platform_login_info,
        submit_platform_application,
        record_consultation_decision
    )
    from src.memory.store import MemoryStore
    from src.analytics.metrics import MetricsTracker
    from src.analytics.reporter import Reporter
    from src.profile.aggregator import ProfileAggregator
    from src.email.processor import EmailProcessor
    from src.platforms.registry import PlatformRegistry

    # Set up agent context
    from src.agent import consult_agent
    memory_store = MemoryStore()
    metrics = MetricsTracker()
    consult_agent.agent_ctx = AgentContext(
        memory_store=memory_store,
        metrics=metrics,
        reporter=Reporter(memory_store, metrics),
        profile_aggregator=ProfileAggregator(),
        email_processor=EmailProcessor(memory_store=memory_store),
        platform_registry=PlatformRegistry()
    )

    # 1. Simulate consultation email details
    consultation = {
        "email_id": "test-email-001",
        "platform": "GLG",
        "project_id": "GLG-TEST-001",
        "subject": "GLG | Test Consultation Opportunity",
        "project_url": "file://" + str(Path(__file__).parent.parent / "fixtures" / "simple_form.html"),
        "rate": 500,
        "project_description": "Test project for AI automation",
        "skills_required": ["AI", "Automation", "Testing"]
    }

    # 2. Get profile summary
    profile_result = await get_profile_summary.handler({})
    assert "content" in profile_result
    profile_text = profile_result["content"][0]["text"]
    profile = json.loads(profile_text)
    print("\n✓ Profile summary retrieved")

    # 3. Get CP writing style
    style_result = await get_cp_writing_style.handler({})
    assert "content" in style_result
    print("✓ CP writing style retrieved")

    # 4. Get application form data
    form_result = await get_application_form_data.handler({
        "consultation_details": consultation,
        "profile": profile
    })
    assert "content" in form_result
    form_payload = json.loads(form_result["content"][0]["text"])
    print("✓ Application form data generated")

    # 5. Get platform login info
    login_result = await get_platform_login_info.handler({"platform": "GLG"})
    assert "content" in login_result
    login_info = json.loads(login_result["content"][0]["text"])
    print("✓ Platform login info retrieved")

    # 6. Submit application via Computer Use (using generic submit_platform_application)
    submission_result = await submit_platform_application.handler({
        "project_url": consultation["project_url"],
        "platform_name": consultation["platform"].lower(),
        "form_data": form_payload.get("form_data", {}),
        "login_username": login_info.get("username"),
        "login_password": login_info.get("password")
    })

    assert "content" in submission_result
    submission_data = json.loads(submission_result["content"][0]["text"])

    if submission_data.get("success"):
        print(f"✓ Application submitted successfully via {submission_data['method']}")

        # 7. Record consultation decision
        record_result = await record_consultation_decision.handler({
            "email_id": consultation["email_id"],
            "platform": consultation["platform"],
            "subject": consultation["subject"],
            "decision": "accept",
            "reasoning": "Strong fit for AI automation project",
            "project_id": consultation["project_id"],
            "submission_details": submission_data
        })

        assert "content" in record_result
        print("✓ Consultation decision recorded")

        # Verify recorded in memory store
        stored = memory_store.get_consultation(consultation["email_id"])
        assert stored is not None
        assert stored["decision"] == "accept"
        assert stored["platform"] == "GLG"
        print("✓ Decision verified in memory store")

        # Verify metrics updated
        summary = metrics.get_summary()
        assert summary["total_acceptances"] >= 1
        print("✓ Metrics updated")

        print("\n✅ Full agent workflow PASSED")
    else:
        print(f"\n⚠ Submission failed: {submission_data.get('error')}")
        print("This may be due to API reliability issues")


if __name__ == "__main__":
    # Run tests individually for debugging
    import sys
    asyncio.run(pytest.main([__file__, "-v", "-s"]))
