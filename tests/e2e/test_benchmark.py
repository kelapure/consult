"""
Gemini vs Claude Computer Use Benchmark (Phase 3.22).

Runs both implementations on the same test form multiple times and compares:
- Success rate
- Average actions taken
- Average execution time
- Error types/frequencies
- Cost estimates
"""

import asyncio
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import pytest
from dotenv import load_dotenv

from src.browser.computer_use import BrowserAutomation

load_dotenv()


class BenchmarkResult:
    """Container for benchmark metrics."""

    def __init__(self, method: str):
        self.method = method
        self.runs: List[Dict[str, Any]] = []
        self.successes = 0
        self.failures = 0
        self.errors: List[str] = []

    def add_run(self, success: bool, actions: int, duration: float, error: str = None):
        """Record a single run."""
        self.runs.append({
            "success": success,
            "actions": actions,
            "duration": duration,
            "error": error
        })
        if success:
            self.successes += 1
        else:
            self.failures += 1
            if error:
                self.errors.append(error)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = len(self.runs)
        return (self.successes / total * 100) if total > 0 else 0.0

    @property
    def avg_actions(self) -> float:
        """Average number of actions for successful runs."""
        successful_actions = [r["actions"] for r in self.runs if r["success"]]
        return statistics.mean(successful_actions) if successful_actions else 0.0

    @property
    def avg_duration(self) -> float:
        """Average execution time in seconds."""
        durations = [r["duration"] for r in self.runs]
        return statistics.mean(durations) if durations else 0.0

    @property
    def median_duration(self) -> float:
        """Median execution time in seconds."""
        durations = [r["duration"] for r in self.runs]
        return statistics.median(durations) if durations else 0.0

    def summary(self) -> str:
        """Generate summary report."""
        return f"""
{self.method} Benchmark Results
{'=' * 50}
Total Runs:       {len(self.runs)}
Successes:        {self.successes}
Failures:         {self.failures}
Success Rate:     {self.success_rate:.1f}%
Avg Actions:      {self.avg_actions:.1f}
Avg Duration:     {self.avg_duration:.1f}s
Median Duration:  {self.median_duration:.1f}s
Common Errors:    {self._error_summary()}
"""

    def _error_summary(self) -> str:
        """Summarize error types."""
        if not self.errors:
            return "None"
        # Count unique error types
        error_counts = {}
        for error in self.errors:
            # Extract first line of error as type
            error_type = error.split('\n')[0][:50]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return "\n    ".join([f"{count}x {err}" for err, count in error_counts.items()])


async def run_single_test(browser: BrowserAutomation, method: str, url: str,
                         task: str, max_iterations: int = 50, headless: bool = True) -> Dict[str, Any]:
    """
    Run a single test with either Gemini or Claude.

    Returns:
        Dict with success, actions, duration, error
    """
    start_time = time.time()

    try:
        await browser.start_browser(headless=headless)

        if method == "gemini":
            success, action_list = await browser.gemini_computer_use(
                task=task,
                url=url,
                max_iterations=max_iterations
            )
        elif method == "claude":
            success, action_list = await browser.claude_computer_use(
                task=task,
                url=url,
                max_iterations=max_iterations
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        duration = time.time() - start_time
        actions = len(action_list)

        return {
            "success": success,
            "actions": actions,
            "duration": duration,
            "error": None
        }

    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "actions": 0,
            "duration": duration,
            "error": str(e)
        }

    finally:
        await browser.close_browser()


@pytest.mark.asyncio
@pytest.mark.slow  # Mark as slow test (can be skipped with -m "not slow")
async def test_gemini_vs_claude_benchmark(complex_form_url: str):
    """
    Benchmark Gemini vs Claude on complex form (reduced runs for faster testing).

    Run with: pytest tests/e2e/test_benchmark.py -v -s
    Skip with: pytest -m "not slow"
    """
    # Use fewer runs for CI/testing (increase to 30 for full benchmark)
    num_runs = 3  # Change to 30 for production benchmark
    task = """
    Fill out and submit this consultation application form completely.

    Steps:
    1. Accept cookies if banner appears
    2. Fill in all text fields with realistic information
    3. Select appropriate options from ALL dropdowns
    4. Fill the textarea with expertise description
    5. Check ALL consultation format preferences
    6. Select a consultation duration
    7. Check both required checkboxes (terms and compliance)
    8. Submit the form
    9. Verify success message appears
    """

    # Initialize results
    gemini_results = BenchmarkResult("Gemini")
    claude_results = BenchmarkResult("Claude")

    print(f"\n{'='*70}")
    print(f"Running Benchmark: {num_runs} runs each (Gemini vs Claude)")
    print(f"{'='*70}\n")

    # Run Gemini tests
    print(f"Testing Gemini Computer Use ({num_runs} runs)...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ", flush=True)
        browser = BrowserAutomation()
        result = await run_single_test(
            browser=browser,
            method="gemini",
            url=complex_form_url,
            task=task,
            max_iterations=50,
            headless=True
        )
        gemini_results.add_run(**result)
        status = "✓" if result["success"] else "✗"
        print(f"{status} ({result['actions']} actions, {result['duration']:.1f}s)")

    # Run Claude tests
    print(f"\nTesting Claude Computer Use ({num_runs} runs)...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ", flush=True)
        browser = BrowserAutomation()
        result = await run_single_test(
            browser=browser,
            method="claude",
            url=complex_form_url,
            task=task,
            max_iterations=50,
            headless=True
        )
        claude_results.add_run(**result)
        status = "✓" if result["success"] else "✗"
        print(f"{status} ({result['actions']} actions, {result['duration']:.1f}s)")

    # Print summary
    print("\n" + gemini_results.summary())
    print(claude_results.summary())

    # Comparison
    print(f"Comparison")
    print(f"{'='*50}")
    print(f"Success Rate:  Claude {claude_results.success_rate:.1f}% vs Gemini {gemini_results.success_rate:.1f}%")
    print(f"Avg Actions:   Claude {claude_results.avg_actions:.1f} vs Gemini {gemini_results.avg_actions:.1f}")
    print(f"Avg Duration:  Claude {claude_results.avg_duration:.1f}s vs Gemini {gemini_results.avg_duration:.1f}s")

    # Save detailed results to file
    results_dir = Path("test_results")
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"benchmark_{timestamp}.txt"

    with open(results_file, "w") as f:
        f.write(f"Benchmark Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*70}\n\n")
        f.write(gemini_results.summary())
        f.write("\n")
        f.write(claude_results.summary())
        f.write("\nComparison\n")
        f.write(f"{'='*50}\n")
        f.write(f"Success Rate:  Claude {claude_results.success_rate:.1f}% vs Gemini {gemini_results.success_rate:.1f}%\n")
        f.write(f"Avg Actions:   Claude {claude_results.avg_actions:.1f} vs Gemini {gemini_results.avg_actions:.1f}\n")
        f.write(f"Avg Duration:  Claude {claude_results.avg_duration:.1f}s vs Gemini {gemini_results.avg_duration:.1f}s\n")

    print(f"\nDetailed results saved to: {results_file}")

    # Basic assertions - at least one method should have decent success rate
    assert claude_results.success_rate > 0 or gemini_results.success_rate > 0, \
        "At least one method should have successful runs"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_form_benchmark(simple_form_url: str):
    """
    Quick benchmark on simple form (faster for CI).

    Run with: pytest tests/e2e/test_benchmark.py::test_simple_form_benchmark -v -s
    """
    num_runs = 5
    task = "Fill out the form with name 'John Doe', email 'john@example.com', age '30', and submit it."

    # Initialize results
    gemini_results = BenchmarkResult("Gemini")
    claude_results = BenchmarkResult("Claude")

    print(f"\n{'='*70}")
    print(f"Simple Form Benchmark: {num_runs} runs each")
    print(f"{'='*70}\n")

    # Run Gemini tests
    print(f"Testing Gemini...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ", flush=True)
        browser = BrowserAutomation()
        result = await run_single_test(
            browser=browser,
            method="gemini",
            url=simple_form_url,
            task=task,
            max_iterations=20,
            headless=True
        )
        gemini_results.add_run(**result)
        status = "✓" if result["success"] else "✗"
        print(f"{status} ({result['actions']} actions, {result['duration']:.1f}s)")

    # Run Claude tests
    print(f"\nTesting Claude...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ", flush=True)
        browser = BrowserAutomation()
        result = await run_single_test(
            browser=browser,
            method="claude",
            url=simple_form_url,
            task=task,
            max_iterations=20,
            headless=True
        )
        claude_results.add_run(**result)
        status = "✓" if result["success"] else "✗"
        print(f"{status} ({result['actions']} actions, {result['duration']:.1f}s)")

    # Print summary
    print("\n" + gemini_results.summary())
    print(claude_results.summary())

    # Both should have high success rate on simple form
    assert claude_results.success_rate >= 60, f"Claude success rate too low: {claude_results.success_rate}%"
    # Note: Gemini may have API reliability issues, so we don't assert on it
