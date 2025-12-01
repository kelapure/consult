import os
import sys
import argparse
import base64
from typing import List, Dict, Optional
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

# Platform queries map
PLATFORM_QUERIES = {
    'glg': 'from:glgroup.com',
    'guidepoint': '(from:guidepointglobal.com OR from:guidepoint.com)',
    'coleman': '(from:colemanrg.com OR from:visasq.com)',
    'alphasights': 'from:alphasights.com',
    'office_hours': 'from:officehours.com',
    'all': '(from:glgroup.com OR from:guidepointglobal.com OR from:guidepoint.com OR from:colemanrg.com OR from:alphasights.com OR from:officehours.com)'
}

def get_message_summary(client: GmailClient, message_id: str) -> Dict:
    """Get subject and date for a message to display to user"""
    try:
        # Use existing client method if possible or raw API for speed
        # The client._get_email_details fetches full body which is slow for just listing
        # Let's use raw API for lightweight fetch
        msg = client.service.users().messages().get(
            userId='me', 
            id=message_id, 
            format='metadata',
            metadataHeaders=['Subject', 'Date', 'From']
        ).execute()
        
        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        
        return {
            'id': message_id,
            'subject': subject,
            'date': date,
            'sender': sender
        }
    except Exception as e:
        logger.warning(f"Could not fetch details for {message_id}: {e}")
        return {'id': message_id, 'subject': 'Error fetching details', 'date': '', 'sender': ''}

def process_platform_emails(platform: str, dry_run: bool = False, force: bool = False, action: str = 'archive'):
    load_dotenv()
    
    # Validate platform
    query = PLATFORM_QUERIES.get(platform.lower())
    if not query:
        logger.error(f"Unknown platform: {platform}. Available: {list(PLATFORM_QUERIES.keys())}")
        return

    # Initialize client
    try:
        client = GmailClient()
        if not client.authenticate():
            logger.error("Authentication failed")
            return
    except Exception as e:
        logger.error(f"Failed to initialize Gmail client: {e}")
        return

    # Search for emails in INBOX
    full_query = f"in:inbox {query}"
    logger.info(f"Searching for emails: {full_query}")
    
    try:
        # Fetch all matching messages
        messages = []
        request = client.service.users().messages().list(userId='me', q=full_query)
        
        while request is not None:
            response = request.execute()
            if 'messages' in response:
                messages.extend(response['messages'])
            request = client.service.users().messages().list_next(request, response)
            
        if not messages:
            logger.info("No emails found matching query.")
            return

        logger.info(f"Found {len(messages)} emails. Fetching details...")
        
        # Process in batches for display
        to_process_ids = []
        
        action_verb = "archive" if action == 'archive' else "delete (move to trash)"
        print(f"\nEmails to be {action_verb}d:")
        print("-" * 100)
        print(f"{'ID':<18} | {'Date':<25} | {'Sender':<30} | {'Subject'}")
        print("-" * 100)
        
        for msg in messages:
            details = get_message_summary(client, msg['id'])
            # Truncate subject/sender for display
            sender = (details['sender'][:27] + '...') if len(details['sender']) > 27 else details['sender']
            subject = (details['subject'][:50] + '...') if len(details['subject']) > 50 else details['subject']
            
            print(f"{details['id']:<18} | {details['date'][:25]:<25} | {sender:<30} | {subject}")
            to_process_ids.append(details['id'])

        print("-" * 100)
        print(f"Total emails found: {len(to_process_ids)}")

        if dry_run:
            logger.info("[DRY RUN] No changes made.")
            return

        # Confirmation step
        if not force:
            confirm = input(f"\nAre you sure you want to {action_verb} these {len(to_process_ids)} emails? [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Operation cancelled by user.")
                return

        # Execute action (archive or delete)
        logger.info(f"{action.capitalize()}ing emails...")
        success_count = 0
        fail_count = 0
        
        # Batch modify is much more efficient than individual calls
        # 1000 message limit per batch
        batch_size = 1000
        for i in range(0, len(to_process_ids), batch_size):
            batch_ids = to_process_ids[i:i + batch_size]
            try:
                body = {'ids': batch_ids}
                if action == 'archive':
                    body['removeLabelIds'] = ['INBOX']
                elif action == 'delete':
                    body['addLabelIds'] = ['TRASH']
                else:
                    logger.error(f"Invalid action: {action}")
                    return

                client.service.users().messages().batchModify(
                    userId='me',
                    body=body
                ).execute()
                success_count += len(batch_ids)
                logger.info(f"{action.capitalize()}d batch {i//batch_size + 1} ({len(batch_ids)} emails)")
            except Exception as e:
                logger.error(f"Failed to {action} batch: {e}")
                fail_count += len(batch_ids)

        logger.success(f"Operation complete. Successfully {action_verb}d: {success_count}. Failed: {fail_count}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process platform emails from Inbox (archive or delete)')
    parser.add_argument('--platform', type=str, required=True, 
                        choices=list(PLATFORM_QUERIES.keys()),
                        help='Platform to process emails for (or "all")')
    parser.add_argument('--dry-run', action='store_true', 
                        help='List emails but do not perform action')
    parser.add_argument('--force', action='store_true', 
                        help='Skip confirmation prompt')
    parser.add_argument('--action', type=str, default='archive', 
                        choices=['archive', 'delete'],
                        help='Action to perform: archive (default) or delete (move to trash)')
    
    args = parser.parse_args()
    
    process_platform_emails(args.platform, args.dry_run, args.force, args.action)
