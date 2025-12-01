import os
import sys
import argparse
from dotenv import load_dotenv
from loguru import logger

# Add project root to path to allow imports from src
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

def delete_emails(dry_run=False):
    load_dotenv()
    
    try:
        client = GmailClient()
        if not client.authenticate():
            logger.error("Failed to authenticate")
            return

        query = 'from:newsletter@aisecret.us'
        logger.info(f"Searching for emails with query: {query}")
        
        # Initial list
        response = client.service.users().messages().list(
            userId='me',
            q=query
        ).execute()
        
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])
        
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = client.service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token
            ).execute()
            if 'messages' in response:
                messages.extend(response['messages'])
        
        count = len(messages)
        
        if count == 0:
            logger.info("No emails found matching the query.")
            return

        logger.info(f"Found {count} emails matching query '{query}'.")

        if dry_run:
            logger.info(f"[DRY RUN] Would move {count} emails to TRASH.")
            logger.info("[DRY RUN] No changes made.")
            return

        logger.info(f"Moving {count} emails to TRASH...")
        
        message_ids = [msg['id'] for msg in messages]
        
        # batchModify has a limit of 1000 messages per request.
        batch_size = 1000
        deleted_count = 0
        for i in range(0, len(message_ids), batch_size):
            chunk = message_ids[i:i + batch_size]
            client.service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': chunk,
                    'addLabelIds': ['TRASH']
                }
            ).execute()
            deleted_count += len(chunk)
            logger.info(f"Trashed batch {i // batch_size + 1} ({len(chunk)} emails)...")
        
        logger.success(f"Successfully moved {deleted_count} emails to TRASH.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Delete emails from newsletter@aisecret.us')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without deleting')
    args = parser.parse_args()
    
    delete_emails(dry_run=args.dry_run)
