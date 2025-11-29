"""
Complex form test for both Gemini and Claude Computer Use
Tests: cookies, checkboxes, dropdowns, radio buttons, multi-field validation
"""

import asyncio
import sys
import os
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.browser.computer_use import BrowserAutomation
from loguru import logger

load_dotenv()


@pytest.mark.asyncio
async def test_complex_form_gemini():
    """Test Gemini with complex GLG-like form"""
    logger.info("=" * 80)
    logger.info("COMPLEX FORM TEST: Gemini Computer Use")
    logger.info("=" * 80)

    # Path to test fixture
    fixture_path = project_root / "tests" / "fixtures" / "complex_form.html"
    test_url = f"file://{fixture_path}"

    logger.info(f"Test URL: {test_url}")

    # Comprehensive task
    task = """Complete the Expert Network application form with the following information:

FIRST: Accept the cookie banner if it appears.

THEN fill out the form:

Personal Information:
- Full Name: Sarah Johnson
- Email: sarah.johnson@example.com
- Phone: +1-650-555-1234

Professional Background:
- Current Role: Select "VP / Senior Director" from dropdown
- Industry: Select "Technology / Software" from dropdown
- Years of Experience: Select "11-15 years" from dropdown
- Areas of Expertise: "Cloud infrastructure and DevOps, with expertise in Kubernetes, AWS, and microservices architecture. 15 years of experience leading engineering teams."

Availability & Preferences:
- Consultation Format: Check BOTH "Phone consultations" AND "Video conferences" checkboxes
- Preferred Duration: Select the "60 minutes" radio button

Terms & Conditions:
- Check the "Terms of Service and Privacy Policy" checkbox (REQUIRED)
- Check the "confidentiality agreements" checkbox (REQUIRED)
- DO NOT check the marketing checkbox (leave unchecked)

After filling ALL fields correctly, click Submit Application and wait for the success message.
"""

    automation = BrowserAutomation()

    try:
        logger.info("\nStarting Gemini complex form test...")
        success, actions = await automation.gemini_computer_use(
            task=task,
            url=test_url,
            max_iterations=50  # Complex form needs more iterations
        )

        logger.info("\n" + "=" * 80)
        logger.info("GEMINI TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Success: {success}")
        logger.info(f"Total actions: {len(actions)}")
        logger.info("\nAction summary:")
        action_types = {}
        for action in actions:
            action_name = action.get('action', 'unknown')
            action_types[action_name] = action_types.get(action_name, 0) + 1

        for action_name, count in sorted(action_types.items()):
            logger.info(f"  {action_name}: {count}")

        if success:
            logger.success("✅ GEMINI TEST PASSED: Complex form completed!")
        else:
            logger.error("❌ GEMINI TEST FAILED: Form not completed")

        return success, len(actions), action_types

    except Exception as e:
        logger.error(f"Gemini test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, {}


@pytest.mark.asyncio
async def test_complex_form_claude():
    """Test Claude with complex GLG-like form"""
    logger.info("\n" + "=" * 80)
    logger.info("COMPLEX FORM TEST: Claude Computer Use")
    logger.info("=" * 80)

    # Path to test fixture
    fixture_path = project_root / "tests" / "fixtures" / "complex_form.html"
    test_url = f"file://{fixture_path}"

    logger.info(f"Test URL: {test_url}")

    # Same task as Gemini
    task = """Complete the Expert Network application form with the following information:

FIRST: Accept the cookie banner if it appears.

THEN fill out the form:

Personal Information:
- Full Name: Sarah Johnson
- Email: sarah.johnson@example.com
- Phone: +1-650-555-1234

Professional Background:
- Current Role: Select "VP / Senior Director" from dropdown
- Industry: Select "Technology / Software" from dropdown
- Years of Experience: Select "11-15 years" from dropdown
- Areas of Expertise: "Cloud infrastructure and DevOps, with expertise in Kubernetes, AWS, and microservices architecture. 15 years of experience leading engineering teams."

Availability & Preferences:
- Consultation Format: Check BOTH "Phone consultations" AND "Video conferences" checkboxes
- Preferred Duration: Select the "60 minutes" radio button

Terms & Conditions:
- Check the "Terms of Service and Privacy Policy" checkbox (REQUIRED)
- Check the "confidentiality agreements" checkbox (REQUIRED)
- DO NOT check the marketing checkbox (leave unchecked)

After filling ALL fields correctly, click Submit Application and wait for the success message.
"""

    automation = BrowserAutomation()

    try:
        logger.info("\nStarting Claude complex form test...")
        success, actions = await automation.claude_computer_use(
            task=task,
            url=test_url,
            max_iterations=50  # Complex form needs more iterations
        )

        logger.info("\n" + "=" * 80)
        logger.info("CLAUDE TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Success: {success}")
        logger.info(f"Total actions: {len(actions)}")
        logger.info("\nAction summary:")
        action_types = {}
        for action in actions:
            action_name = action.get('action', 'unknown')
            action_types[action_name] = action_types.get(action_name, 0) + 1

        for action_name, count in sorted(action_types.items()):
            logger.info(f"  {action_name}: {count}")

        if success:
            logger.success("✅ CLAUDE TEST PASSED: Complex form completed!")
        else:
            logger.error("❌ CLAUDE TEST FAILED: Form not completed")

        return success, len(actions), action_types

    except Exception as e:
        logger.error(f"Claude test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, {}


async def main():
    """Run complex form tests for both Gemini and Claude"""
    logger.info("Running Complex Form Tests (Gemini vs Claude)\n")

    results = {}

    # Test 1: Gemini
    gemini_success, gemini_actions, gemini_types = await test_complex_form_gemini()
    results['Gemini'] = gemini_success

    # Test 2: Claude
    claude_success, claude_actions, claude_types = await test_complex_form_claude()
    results['Claude'] = claude_success

    # Comparison summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"{'Method':<15} {'Status':<15} {'Actions':<10} {'Result'}")
    print("-" * 80)

    gemini_status = "✅ PASS" if gemini_success else "❌ FAIL"
    claude_status = "✅ PASS" if claude_success else "❌ FAIL"

    print(f"{'Gemini':<15} {gemini_status:<15} {gemini_actions:<10}")
    print(f"{'Claude':<15} {claude_status:<15} {claude_actions:<10}")

    print("\n" + "=" * 80)
    print("FEATURE ANALYSIS")
    print("=" * 80)

    features_tested = [
        "✓ Cookie consent banner",
        "✓ Text inputs (name, email, phone)",
        "✓ Multiple dropdowns (3 selects)",
        "✓ Textarea (expertise)",
        "✓ Multiple checkboxes (2 formats)",
        "✓ Radio buttons (duration)",
        "✓ Required checkboxes (terms, compliance)",
        "✓ Form validation"
    ]

    for feature in features_tested:
        print(feature)

    print("\n" + "=" * 80)
    print("MISSING FEATURES / FAILURES")
    print("=" * 80)

    if not gemini_success:
        print("Gemini struggled with:")
        print(f"  - Check action logs above for details")

    if not claude_success:
        print("Claude struggled with:")
        print(f"  - Check action logs above for details")

    if gemini_success and claude_success:
        print("Both implementations handled all features successfully!")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} implementations passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
