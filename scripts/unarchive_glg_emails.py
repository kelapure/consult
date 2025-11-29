#!/usr/bin/env python3
"""Utility script to unarchive GLG emails from the last 14 days"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv
from src.email.gmail_client import GmailClient

# Load environment variables
load_dotenv()


def unarchive_glg_emails(days_back: int = 14):
    """Find and unarchive GLG emails from the last N days"""
    gmail = GmailClient()

    # Authenticate
    if not gmail.authenticate():
        logger.error("Gmail authentication failed")
        return False

    # Calculate date range
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

    # Search for archived GLG emails (not in INBOX)
    query = f'after:{start_date} from:glgroup.com -in:inbox'
    logger.info(f"Searching for archived GLG emails with query: {query}")

    try:
        results = gmail.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=500
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            logger.info("No archived GLG emails found")
            return True

        logger.info(f"Found {len(messages)} archived GLG emails")

        # Unarchive each email
        for i, msg in enumerate(messages, 1):
            email_id = msg['id']
            logger.info(f"[{i}/{len(messages)}] Unarchiving email: {email_id}")
            gmail.unarchive_email(email_id)

        logger.success(f"Successfully unarchived {len(messages)} GLG emails")
        return True

    except Exception as e:
        logger.error(f"Error searching for archived emails: {e}")
        return False


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    logger.info(f"Unarchiving GLG emails from last {days} days")
    success = unarchive_glg_emails(days)
    sys.exit(0 if success else 1)
