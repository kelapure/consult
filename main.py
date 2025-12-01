#!/usr/bin/env python3
"""Main entry point for consultation automation agent"""

import asyncio
import os
import sys
import argparse
import json
from loguru import logger
from dotenv import load_dotenv

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/consultation_json_{time}.log", rotation="1 day", retention="7 days", level="DEBUG", serialize=True)

# Load environment variables
load_dotenv()


def validate_and_export_credentials():
    """Validate critical credentials exist and export to subprocess environment."""
    critical_vars = [
        'ANTHROPIC_API_KEY',
        'GMAIL_EMAIL',
        'GOOGLE_API_KEY'
    ]

    platform_vars = {
        'glg': ['GLG_USERNAME', 'GLG_PASSWORD', 'GLG_LOGIN_URL', 'GLG_DASHBOARD_URL'],
        'guidepoint': ['GUIDEPOINT_USERNAME', 'GUIDEPOINT_PASSWORD', 'GUIDEPOINT_LOGIN_URL', 'GUIDEPOINT_DASHBOARD_URL'],
        'coleman': ['COLEMAN_USERNAME', 'COLEMAN_PASSWORD', 'COLEMAN_LOGIN_URL', 'COLEMAN_DASHBOARD_URL'],
        'office_hours': ['OFFICE_HOURS_DASHBOARD_URL']
    }

    # Check critical variables
    missing_vars = []
    for var in critical_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            os.environ[var] = value  # Ensure subprocess inheritance

    # Log credential status
    for platform, vars_list in platform_vars.items():
        available = []
        missing = []
        for var in vars_list:
            value = os.getenv(var)
            if value:
                available.append(var)
                os.environ[var] = value  # Export to subprocess
            else:
                missing.append(var)

        if available:
            logger.info(f"{platform.upper()} credentials: {len(available)}/{len(vars_list)} available")
        if missing:
            logger.warning(f"{platform.upper()} missing: {missing}")

    if missing_vars:
        logger.error(f"Critical variables missing: {missing_vars}")
        return False

    logger.info("Credentials validated and exported to subprocess environment")
    return True


# Custom JSON formatter for correlation_id (will be used by the serialize=True sink)
def json_formatter(record):
    record["extra"]["correlation_id"] = record["extra"].get("correlation_id", "N/A")
    return json.dumps(record["extra"]) + "\n"

from src.agent.consult_agent import run_consult_agent
from src.memory.store import MemoryStore
from src.analytics.metrics import MetricsTracker
from src.analytics.reporter import Reporter


async def main():
    """Main entry point"""
    # Validate and export environment variables for subprocess inheritance
    if not validate_and_export_credentials():
        logger.error("Environment validation failed")
        return 1

    parser = argparse.ArgumentParser(description='Consultation Automation Agent')
    parser.add_argument('--days', type=int, default=14, help='Days to look back for emails')
    parser.add_argument('--report-only', action='store_true', help='Generate report only (no processing)')
    parser.add_argument('--view-metrics', type=int, metavar='DAYS', help='View aggregated metrics for last N days')
    parser.add_argument('--view-runs', type=int, metavar='COUNT', help='View last N runs (default: 10)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode (no UI)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode (save screenshots, verbose logging)')
    parser.add_argument('--platform', type=str, choices=['glg', 'guidepoint', 'coleman', 'office_hours'], help='Focus on a specific platform (glg, guidepoint, coleman, or office_hours)')
    parser.add_argument('--mode', type=str, choices=['email', 'dashboard'], default='email',
                        help='Processing mode: email (default) or dashboard (batch process all invitations)')
    args = parser.parse_args()

    # Validate: dashboard mode requires --platform
    if args.mode == 'dashboard' and not args.platform:
        parser.error("Dashboard mode requires --platform flag")

    # Configure environment based on flags
    if args.headless:
        os.environ['HEADLESS'] = 'true'
        logger.info("Running in HEADLESS mode (no browser UI)")

    if args.debug:
        os.environ['DEBUG'] = 'true'
        # Reconfigure logger for debug mode
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        logger.add("logs/consultation_json_{time}.log", rotation="1 day", retention="7 days", level="DEBUG", serialize=True)
        logger.debug("DEBUG mode enabled (screenshots will be saved, verbose logging active)")

    try:
        # View aggregated metrics
        if args.view_metrics is not None:
            memory_store = MemoryStore()
            metrics = MetricsTracker()
            reporter = Reporter(memory_store, metrics)
            await reporter.display_aggregated_metrics(days=args.view_metrics)
            return 0

        # View recent runs
        if args.view_runs is not None:
            memory_store = MemoryStore()
            metrics = MetricsTracker()
            reporter = Reporter(memory_store, metrics)
            await reporter.display_recent_runs(limit=args.view_runs)
            return 0

        # Generate report only
        if args.report_only:
            memory_store = MemoryStore()
            metrics = MetricsTracker()
            reporter = Reporter(memory_store, metrics)
            # Use the more flexible generate_daily_report with default date range for now
            # Will be enhanced further to accept command line arguments for dates/platform
            report = await reporter.generate_daily_report(send_email=False, start_date=None, end_date=None, platform_filter=None)
            logger.info("Report generated")
            return 0

        # Validate platform-specific credentials before starting agent
        if args.platform:
            platform = args.platform.lower()

            if platform == 'office_hours':
                if not os.getenv(f"{platform.upper()}_DASHBOARD_URL"):
                    logger.error(f"Missing {platform.upper()}_DASHBOARD_URL for Google OAuth platform")
                    return 1
                logger.info(f"{platform.upper()} uses Google OAuth - dashboard URL validated")
            else:
                required_vars = [f"{platform.upper()}_USERNAME", f"{platform.upper()}_PASSWORD"]
                missing = [var for var in required_vars if not os.getenv(var)]

                if missing:
                    logger.error(f"Missing credentials for {platform.upper()}: {missing}")
                    logger.error(f"Please ensure these are set in .env file: {missing}")
                    return 1

                logger.info(f"{platform.upper()} platform credentials validated")

        # Run automation via Agent SDK
        platform_msg = f" (focusing on {args.platform.upper()})" if args.platform else ""
        mode_msg = f" in {args.mode.upper()} mode" if args.mode != 'email' else ""
        logger.info(f"Starting consultation automation (processing last {args.days} days){platform_msg}{mode_msg}")
        result = await run_consult_agent(days_back=args.days, platform_filter=args.platform, mode=args.mode)

        if result:
            logger.success(f"Processed {result.get('emails_processed', 0)} emails")
            logger.success(f"Consultations processed: {result.get('total_consultations', 0)}")
            logger.success(f"Execution time: {result.get('avg_response_time_seconds', 0):.1f}s")
            return 0
        else:
            logger.error("Execution failed: No metrics returned")
            return 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
