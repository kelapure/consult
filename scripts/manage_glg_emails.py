#!/usr/bin/env python3
"""
GLG Email Management Script

This script identifies GLG opportunities from the last 30 days and allows for archiving them.
Usage: python scripts/manage_glg_emails.py [--dry-run] [--days N]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from email.processor import EmailProcessor
from email.gmail_client import GmailClient
from platforms.registry import PlatformRegistry
from email.parser import EmailParser


class GLGEmailManager:
    def __init__(self):
        self.email_processor = EmailProcessor()
        self.gmail_client = self.email_processor.gmail
        self.platform_registry = PlatformRegistry()
        self.parser = EmailParser()

    def authenticate(self) -> bool:
        """Authenticate with Gmail API"""
        print("Authenticating with Gmail...")
        success = self.gmail_client.authenticate()
        if success:
            print("✅ Gmail authentication successful")
            return True
        else:
            print("❌ Gmail authentication failed")
            return False

    def fetch_glg_opportunities(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Fetch and identify GLG opportunities from the last N days"""
        print(f"Fetching consultation emails from last {days_back} days...")

        # Get all consultation emails from the period
        all_emails = self.gmail_client.search_consultation_emails(days_back=days_back)
        print(f"Found {len(all_emails)} total consultation emails")

        # Filter for GLG only and enrich with details
        glg_emails = []
        for email in all_emails:
            # Detect platform
            platform = self.platform_registry.detect_platform(email)
            if platform == 'glg':
                # Parse consultation details
                details = self.parser.parse_consultation_details(email['bodyText'])

                # Enrich email with parsed details
                enriched_email = {
                    'id': email['id'],
                    'subject': email['subject'],
                    'sender': email['sender'],
                    'sender_email': email['sender_email'],
                    'date': email['date'],
                    'platform': 'glg',
                    'project_url': details.get('project_url'),
                    'project_id': details.get('project_id'),
                    'skills_required': details.get('skills_required', []),
                    'duration': details.get('duration', 'Unknown'),
                    'budget': details.get('budget', 'Unknown'),
                    'snippet': email.get('snippet', ''),
                    'bodyText': email['bodyText'][:500] + "..." if len(email['bodyText']) > 500 else email['bodyText']
                }
                glg_emails.append(enriched_email)

        print(f"Found {len(glg_emails)} GLG opportunities")
        return glg_emails

    def display_opportunities(self, glg_emails: List[Dict[str, Any]]) -> None:
        """Display GLG opportunities in a formatted list"""
        if not glg_emails:
            print("No GLG opportunities found in the specified period.")
            return

        print("\n" + "="*80)
        print(f"GLG OPPORTUNITIES FOUND ({len(glg_emails)} total)")
        print("="*80)

        for i, email in enumerate(glg_emails, 1):
            print(f"\n{i}. {email['subject']}")
            print(f"   From: {email['sender']} ({email['sender_email']})")
            print(f"   Date: {email['date']}")
            print(f"   Email ID: {email['id']}")

            if email.get('project_id'):
                print(f"   Project ID: {email['project_id']}")
            if email.get('project_url'):
                print(f"   Project URL: {email['project_url']}")
            if email.get('skills_required'):
                print(f"   Skills: {', '.join(email['skills_required'][:5])}{'...' if len(email['skills_required']) > 5 else ''}")
            if email.get('duration') and email.get('duration') != 'Unknown':
                print(f"   Duration: {email['duration']}")
            if email.get('budget') and email.get('budget') != 'Unknown':
                print(f"   Budget: {email['budget']}")

            print(f"   Preview: {email['snippet']}")
            print("-" * 80)

    def get_user_confirmation(self, glg_emails: List[Dict[str, Any]]) -> List[str]:
        """Get user confirmation for which emails to archive"""
        if not glg_emails:
            return []

        print(f"\nFound {len(glg_emails)} GLG emails. Choose archiving options:")
        print("1. Archive ALL GLG emails")
        print("2. Select specific emails to archive")
        print("3. Cancel (don't archive anything)")

        while True:
            choice = input("\nEnter your choice (1-3): ").strip()

            if choice == "1":
                # Archive all
                email_ids = [email['id'] for email in glg_emails]
                confirm = input(f"Are you sure you want to archive ALL {len(email_ids)} GLG emails? (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    return email_ids
                else:
                    print("Cancelled.")
                    return []

            elif choice == "2":
                # Select specific emails
                print("\nSelect emails to archive (enter numbers separated by commas, e.g., 1,3,5):")
                indices_str = input("Email numbers: ").strip()

                try:
                    indices = [int(x.strip()) - 1 for x in indices_str.split(',') if x.strip()]
                    selected_emails = [glg_emails[i] for i in indices if 0 <= i < len(glg_emails)]

                    if selected_emails:
                        print(f"\nSelected {len(selected_emails)} emails:")
                        for email in selected_emails:
                            print(f"  - {email['subject']}")

                        confirm = input(f"Archive these {len(selected_emails)} emails? (yes/no): ").strip().lower()
                        if confirm in ['yes', 'y']:
                            return [email['id'] for email in selected_emails]
                        else:
                            print("Cancelled.")
                            return []
                    else:
                        print("No valid emails selected.")

                except (ValueError, IndexError):
                    print("Invalid selection. Please enter valid email numbers.")

            elif choice == "3":
                print("Cancelled.")
                return []
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def archive_emails(self, email_ids: List[str], dry_run: bool = False) -> None:
        """Archive the specified emails"""
        if not email_ids:
            print("No emails to archive.")
            return

        if dry_run:
            print(f"\n[DRY RUN] Would archive {len(email_ids)} emails:")
            for email_id in email_ids:
                print(f"  - Email ID: {email_id}")
            return

        print(f"\nArchiving {len(email_ids)} emails...")

        successful = 0
        failed = 0

        for i, email_id in enumerate(email_ids, 1):
            try:
                print(f"  Archiving {i}/{len(email_ids)}: {email_id}")
                self.gmail_client.archive_email(email_id)
                successful += 1
            except Exception as e:
                print(f"  ❌ Failed to archive {email_id}: {str(e)}")
                failed += 1

        print(f"\nArchiving complete:")
        print(f"  ✅ Successfully archived: {successful}")
        if failed > 0:
            print(f"  ❌ Failed to archive: {failed}")

    def save_report(self, glg_emails: List[Dict[str, Any]], archived_ids: List[str]) -> None:
        """Save a report of the GLG email management session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"reports/glg_email_report_{timestamp}.json"

        # Ensure reports directory exists
        Path("reports").mkdir(exist_ok=True)

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_glg_emails_found": len(glg_emails),
            "emails_archived": len(archived_ids),
            "glg_emails": glg_emails,
            "archived_email_ids": archived_ids
        }

        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"\nReport saved to: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Manage GLG emails - identify and archive GLG opportunities')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be archived without actually archiving')
    parser.add_argument('--days', type=int, default=30, help='Number of days back to search (default: 30)')

    args = parser.parse_args()

    print("GLG Email Manager")
    print("================")

    if args.dry_run:
        print("🔍 DRY RUN MODE - No emails will actually be archived")

    manager = GLGEmailManager()

    # Authenticate with Gmail
    if not manager.authenticate():
        return 1

    # Fetch GLG opportunities
    glg_emails = manager.fetch_glg_opportunities(days_back=args.days)

    # Display opportunities
    manager.display_opportunities(glg_emails)

    if glg_emails:
        # Get user confirmation for archiving
        email_ids_to_archive = manager.get_user_confirmation(glg_emails)

        # Archive emails
        manager.archive_emails(email_ids_to_archive, dry_run=args.dry_run)

        # Save report
        manager.save_report(glg_emails, email_ids_to_archive)

    print("\nGLG Email management completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())