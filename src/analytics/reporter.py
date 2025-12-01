"""Analytics and reporting"""

import os
import csv
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from .metrics import MetricsTracker
from ..memory.store import MemoryStore
from ..email.gmail_client import GmailClient


class Reporter:
    """Generate reports and analytics"""

    def __init__(self, memory_store: MemoryStore, metrics: MetricsTracker):
        """Initialize reporter"""
        self.memory = memory_store
        self.metrics = metrics
        self.gmail_client = GmailClient()
        self.reports_dir = Path('reports')
        self.reports_dir.mkdir(exist_ok=True)
        logger.info("Reporter initialized")

    async def display_recent_runs(self, limit: int = 10):
        """Display recent consultation runs"""
        consultations = self.memory.get_recent_consultations(limit)
        
        if not consultations:
            print("No recent runs found.")
            return
            
        print(f"Displaying last {len(consultations)} runs:\n")
        
        # Headers
        headers = ["#", "Project", "Rate", "Status"]
        
        # Column widths
        widths = {
            "#": 3,
            "Project": 40,
            "Rate": 10,
            "Status": 80  # Increased width for log file path
        }
        
        # Print header
        header_line = " | ".join(f"{h:<{widths[h]}}" for h in headers)
        print(header_line)
        print("-" * len(header_line))
        
        for i, run in enumerate(consultations, 1):
            subject = run.get('subject', 'N/A')
            # Truncate subject if too long
            if len(subject) > widths["Project"] - 1:
                subject = subject[:widths["Project"] - 4] + "..."
            
            # Extract rate from submission details or subject
            rate = "varies"
            if "submission_details" in run and isinstance(run["submission_details"], dict):
                # Example: submission_details might have a rate field
                rate_info = run["submission_details"].get("rate")
                if isinstance(rate_info, (int, float)):
                    rate = f"${rate_info}/hr"
                elif isinstance(rate_info, str):
                    rate = rate_info

            status = "Unknown"
            if run.get('application_submitted'):
                status = "Recorded as submitted"
            elif run.get('decision') == 'decline':
                status = "Declined"
            elif run.get('decision') == 'accept' and not run.get('application_submitted'):
                log_file = run.get('submission_details', {}).get('log_file', 'N/A')
                status = f"Browser automation failed. Log: {log_file}"

            row = {
                "#": str(i),
                "Project": subject,
                "Rate": rate,
                "Status": status
            }
            
            row_line = " | ".join(f"{row[h]:<{widths[h]}}" for h in headers)
            print(row_line)
        
        print("\n")

    async def display_aggregated_metrics(self, days: int):
        """Display aggregated metrics for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        metrics = self.memory.get_aggregated_metrics_by_consultation(start_date, end_date)
        
        if not metrics or metrics.get('total_consultations') == 0:
            print(f"No consultation metrics found for the last {days} days.")
            return
            
        print(f"Aggregated Metrics for Last {days} Days\n")
        
        # Key metrics
        print("Overall Performance")
        print("-------------------")
        print(f"  Total Consultations: {metrics['total_consultations']}")
        print(f"  Emails Processed: {metrics['total_emails_processed']}")
        print(f"  Applications Submitted: {metrics['total_applications']}")
        print(f"  Acceptances: {metrics['total_acceptances']}")
        print(f"  Rejections: {metrics['total_rejections']}")
        print(f"  Drafts Created: {metrics['total_drafts_created']}")
        
        # Calculate success rate
        if metrics['total_applications'] > 0:
            success_rate = (metrics['total_acceptances'] / metrics['total_applications']) * 100
            print(f"  Acceptance Rate (of applications): {success_rate:.2f}%")
        else:
            print("  Acceptance Rate (of applications): N/A")
        
        print(f"  Total Failures (browser automation/submission): {metrics['total_failures']}")
        print(f"  Estimated Revenue Potential: ${metrics['revenue_potential']:,.2f}/month")
        print(f"  Average Processing Time: {metrics['avg_response_time_seconds']:.1f}s")
        print("\n")
        
        # By platform
        if metrics['by_platform']:
            print("Activity by Platform")
            print("--------------------")
            for platform, count in metrics['by_platform'].items():
                print(f"  - {platform}: {count} applications")
            print("\n")
            
        # Failure types by component and reason
        if metrics.get('failures_by_component_reason'):
            print("Failures by Component and Reason")
            print("--------------------------------")
            for component, reasons in metrics['failures_by_component_reason'].items():
                print(f"  Component: {component}")
                for reason, count in reasons.items():
                    print(f"    - {reason}: {count} failures")
            print("\n")

    
    async def generate_daily_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        platform_filter: Optional[str] = None,
        send_email: bool = True
    ) -> Dict[str, Any]:
        """
        Generate daily summary report for a given date range and optional platform.
        """
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=1) # Default to last day
        
        # Get aggregated metrics for the specified range
        summary = self.memory.get_aggregated_metrics_by_consultation(start_date, end_date, platform_filter)

        report = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'platform_filter': platform_filter,
            'summary': summary,
            'generated_at': datetime.now().isoformat()
        }
        
        # Generate text report
        text_report = self._format_text_report(report)
        
        # Save to file
        report_filename = f"consultation_report_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        if platform_filter:
            report_filename += f"_{platform_filter}"
        report_file = self.reports_dir / f"{report_filename}.txt"
        with open(report_file, 'w') as f:
            f.write(text_report)
        
        logger.info(f"Consultation report saved to {report_file}")
        
        # Generate CSV
        csv_file = self.reports_dir / f"{report_filename}.csv"
        self._save_csv_report(report, csv_file)

        # Send email if requested
        if send_email:
            self._send_email_report(report, text_report)
        
        return report
    
    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format text report with complete activity details"""
        summary = report['summary']
        start_date_str = datetime.fromisoformat(report['start_date']).strftime('%Y-%m-%d')
        end_date_str = datetime.fromisoformat(report['end_date']).strftime('%Y-%m-%d')
        platform_filter = report['platform_filter']
        
        date_range_str = f"From {start_date_str} to {end_date_str}"
        if platform_filter:
            date_range_str += f" (Platform: {platform_filter.upper()})"
        
        lines = [
            "=" * 80,
            f"CONSULTATION AGENT - COMPLETE ACTIVITY REPORT - {date_range_str}",
            "=" * 80,
            "",
            "EXECUTIVE SUMMARY",
            "-" * 80,
            f"Emails Processed: {summary.get('total_emails_processed', 0)}",
            f"Emails Archived: {summary.get('total_emails_archived', 0)}",
            f"Email Drafts Created: {summary.get('total_drafts_created', 0)}",
            "",
            f"Applications Submitted: {summary['total_applications']}",
            f"Consultations Accepted: {summary['total_acceptances']}",
            f"Consultations Declined: {summary['total_rejections']}",
            f"Surveys Completed: {summary['total_surveys']}",
            f"Errors Encountered: {summary['total_errors']}",
            "",
            f"Acceptance Rate: {summary['acceptance_rate']:.1%}",
            f"Revenue Potential: ${summary['revenue_potential']:,.2f}/month",
            f"Avg Processing Time: {summary['avg_response_time_seconds']:.1f}s",
            "",
            "BY PLATFORM",
            "-" * 80,
        ]
        
        if summary.get('by_platform'):
            for platform, count in summary['by_platform'].items():
                lines.append(f"  {platform}: {count}")
        else:
            lines.append("  No platform activity")
        
        lines.extend([
            "",
            "FORM FILLING STRATEGIES",
            "-" * 80,
        ])
        
        if summary.get('by_strategy'):
            for strategy, count in summary['by_strategy'].items():
                lines.append(f"  {strategy}: {count}")
        else:
            lines.append("  No form filling activity")
        
        # Detailed consultation log (now filtered by date and platform)
        consultations = summary.get('consultations', [])
        if consultations:
            lines.extend([
                "",
                "CONSULTATION DETAILS",
                "-" * 80,
            ])
            
            for i, consultation in enumerate(consultations, 1):
                decision_symbol = "✓" if consultation['decision'] == 'accept' else "✗"
                lines.extend([
                    f"{i}. {decision_symbol} {consultation['subject']}",
                    f"   Platform: {consultation['platform']}",
                    f"   Decision: {consultation['decision'].upper()}",
                    f"   Reasoning: {consultation.get('reasoning', 'N/A')}",
                ])
                # actions_taken is now part of submission_details
                submission_details = consultation.get('submission_details', {})
                if submission_details.get('actions'):
                    # Limit to 5 actions for brevity in the report
                    actions_display = [f"{a['action']} at ({a.get('x','N/A')},{a.get('y','N/A')})" for a in submission_details['actions']][:5]
                    lines.append(f"   Actions: {', '.join(actions_display)}")
                if submission_details.get('log_file'):
                    lines.append(f"   Log File: {submission_details['log_file']}")
                lines.append("")
        
        # Detailed failure log
        if summary.get('failures_by_component_reason'):
            lines.extend([
                "",
                "FAILURES & ERRORS",
                "-" * 80,
            ])
            
            for component, reasons in summary['failures_by_component_reason'].items():
                lines.append(f"\nComponent: {component.upper().replace('_', ' ')}")
                lines.append("-" * 80)
                for reason, count in reasons.items():
                    lines.append(f"  - {reason}: {count} failures")
        
        lines.extend([
            "=" * 80,
            f"Report generated: {report['generated_at']}",
            "=" * 80
        ])
        
        return "\n".join(lines)

    
    def _save_csv_report(self, report: Dict[str, Any], csv_file: Path):
        """Save CSV report"""
        try:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Subject', 'Platform', 'Decision', 'Status'])
                
                for app in report['applications']:
                    writer.writerow([
                        app.get('date', ''),
                        app.get('subject', ''),
                        app.get('platform', ''),
                        app.get('decision', ''),
                        app.get('status', '')
                    ])
            
            logger.info(f"CSV report saved to {csv_file}")
        except Exception as e:
            logger.error(f"Error saving CSV report: {e}")

    def _send_email_report(self, report: Dict[str, Any], text_report: str):
        """Send email report using Gmail API with CP writing style"""
        try:
            report_email = os.getenv('DAILY_REPORT_EMAIL')
            if not report_email:
                logger.warning("DAILY_REPORT_EMAIL not set, skipping email")
                return
            
            summary = report['summary']
            start_date_str = datetime.fromisoformat(report['start_date']).strftime('%Y-%m-%d')
            end_date_str = datetime.fromisoformat(report['end_date']).strftime('%Y-%m-%d')
            platform_filter = report['platform_filter']

            # Format email subject (CP style: clear and direct)
            subject = f"Consultation Agent Report - {start_date_str} to {end_date_str}"
            if platform_filter:
                subject += f" ({platform_filter.upper()})"
            
            # Format email body (CP writing style: data-focused, concise, professional)
            email_body = self._format_email_body(report, summary, start_date_str, end_date_str)
            
            # Attach CSV report if available
            report_filename = f"consultation_report_{start_date_str.replace('-','')}_to_{end_date_str.replace('-','')}"
            if platform_filter:
                report_filename += f"_{platform_filter}"
            csv_file = self.reports_dir / f"{report_filename}.csv"
            attachments = [str(csv_file)] if csv_file.exists() else None
            
            # Send email
            self.gmail_client.send_email(
                to_email=report_email,
                subject=subject,
                body=email_body,
                attachments=attachments
            )
            
            logger.success(f"Consultation report email sent to {report_email}")
            
        except Exception as e:
            logger.error(f"Error sending email report: {e}")
    
    def _format_email_body(self, report: Dict[str, Any], summary: Dict[str, Any], start_date_str: str, end_date_str: str) -> str:
        """
        Format email body following CP writing style guidelines:
        - Clear, concise, data-focused
        - Professional tone
        - Proper hierarchy
        - No jargon
        """
        lines = [
            f"Consultation Agent Report - {start_date_str} to {end_date_str}",
            "",
            "Summary",
            "-" * 40,
            f"Applications: {summary['total_applications']}",
            f"Accepted: {summary['total_acceptances']}",
            f"Rejected: {summary['total_rejections']}",
            f"Acceptance Rate: {summary['acceptance_rate']:.1%}",
            f"Revenue Potential: ${summary['revenue_potential']:,.2f}/month",
            "",
        ]
        
        # Platform breakdown
        if summary.get('by_platform'):
            lines.append("By Platform")
            lines.append("-" * 40)
            for platform, count in summary['by_platform'].items():
                lines.append(f"{platform}: {count}")
            lines.append("")
        
        # Strategy breakdown
        if summary.get('by_strategy'):
            lines.append("Form Filling Strategies")
            lines.append("-" * 40)
            for strategy, count in summary['by_strategy'].items():
                lines.append(f"{strategy}: {count}")
            lines.append("")
        
        # Next steps (CP style: forward-looking)
        lines.extend([
            "Next Steps",
            "-" * 40,
            "Review attached CSV for detailed application data.",
            "Full report saved to reports/ directory.",
            "",
            f"Report generated: {datetime.fromisoformat(report['generated_at']).strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        
        return "\n".join(lines)

