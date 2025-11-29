#!/usr/bin/env python3
"""Main entry point for consultation automation agent"""

import asyncio
import os
import sys
import argparse
from loguru import logger
from dotenv import load_dotenv

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/consultation_json_{time}.log", rotation="1 day", retention="7 days", level="DEBUG", serialize=True)

# Load environment variables
load_dotenv()

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
    parser = argparse.ArgumentParser(description='Consultation Automation Agent')
    parser.add_argument('--days', type=int, default=14, help='Days to look back for emails')
    parser.add_argument('--report-only', action='store_true', help='Generate report only (no processing)')
    parser.add_argument('--view-metrics', type=int, metavar='DAYS', help='View aggregated metrics for last N days')
    parser.add_argument('--view-runs', type=int, metavar='COUNT', help='View last N runs (default: 10)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode (no UI)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode (save screenshots, verbose logging)')
    args = parser.parse_args()

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

        # Run automation via Agent SDK
        logger.info(f"Starting consultation automation (processing last {args.days} days)")
        result = await run_consult_agent(days_back=args.days)

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
