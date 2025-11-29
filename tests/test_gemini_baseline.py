"""
Baseline test for current Gemini implementation
Tests the existing computer use functionality before enhancements
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
async def test_simple_form():
    """Test Gemini filling a simple form"""
    logger.info("=" * 60)
    logger.info("BASELINE TEST: Simple Form with Current Gemini Implementation")
    logger.info("=" * 60)

    # Path to test fixture
    fixture_path = project_root / "tests" / "fixtures" / "simple_form.html"
    test_url = f"file://{fixture_path}"

    logger.info(f"Test URL: {test_url}")

    # Test data
    task = """Fill out the application form with:
- Name: John Smith
- Email: john.smith@example.com
- Relevant Experience: 10 years of software engineering experience in Python and cloud infrastructure

After filling all fields, click the Submit Application button.
Wait for the success message to appear.
"""

    automation = BrowserAutomation()

    try:
        logger.info("\nStarting test...")
        success, actions = await automation.gemini_computer_use(
            task=task,
            url=test_url,
            max_iterations=15
        )

        logger.info("\n" + "=" * 60)
        logger.info("TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Success: {success}")
        logger.info(f"Total actions: {len(actions)}")
        logger.info("\nAction log:")
        for i, action in enumerate(actions, 1):
            logger.info(f"  {i}. {action}")

        if success:
            logger.success("✅ TEST PASSED: Form filled successfully!")
        else:
            logger.error("❌ TEST FAILED: Form not filled")

        return success

    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run baseline tests"""
    logger.info("Running Gemini Computer Use Baseline Tests\n")

    results = {}

    # Test 1: Simple form
    results['simple_form'] = await test_simple_form()

    # Summary
    print("\n" + "=" * 60)
    print("BASELINE TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
