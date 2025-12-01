import os
import sys
import argparse
from dotenv import load_dotenv
from loguru import logger

# Add project root to path to allow imports from src
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

# Define GLG query
GLG_QUERY = 'from:glgroup.com'

def list_and_archive_glg_sample(limit=10, archive=False):
    load_dotenv()
    
    try:
        client = GmailClient()
        if not client.authenticate():
            logger.error("Failed to authenticate")
            return

        # Search only in INBOX
        full_query = f"in:inbox {GLG_QUERY}"
        logger.info(f"Searching for emails: {full_query}")
        
        response = client.service.users().messages().list(
            userId='me', 
            q=full_query,
            maxResults=limit
        ).execute()
        
        messages = response.get('messages', [])
        
        if not messages:
            logger.info("No emails found matching query.")
            return

        logger.info(f"Found {len(messages)} emails. Listing details:")
        
        email_ids = []
        print("\nEmails found:")
        print("-" * 80)
        for msg in messages:
            details = client.service.users().messages().get(
                userId='me', 
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'Date']
            ).execute()
            
            subject = next((h['value'] for h in details['payload']['headers'] if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in details['payload']['headers'] if h['name'] == 'Date'), 'Unknown Date')
            
            print(f"ID: {msg['id']} | Date: {date[:20]} | Subject: {subject[:60]}...")
            email_ids.append(msg['id'])
        print("-" * 80)

        if archive:
            logger.info(f"Archiving these {len(email_ids)} emails...")
            try:
                client.service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': email_ids,
                        'removeLabelIds': ['INBOX']
                    }
                ).execute()
                logger.success(f"Successfully archived {len(email_ids)} emails.")
            except Exception as e:
                logger.error(f"Failed to archive batch: {e}")
        else:
            logger.info("Dry run complete. No emails archived.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Archive first N GLG emails')
    parser.add_argument('--archive', action='store_true', help='Perform archive action')
    args = parser.parse_args()
    
    list_and_archive_glg_sample(archive=args.archive)
