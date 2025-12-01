import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

def debug_list_inbox(limit=20):
    load_dotenv()
    
    client = GmailClient()
    if not client.authenticate():
        logger.error("Failed to authenticate")
        return

    logger.info(f"Listing top {limit} messages in INBOX...")
    
    try:
        response = client.service.users().messages().list(
            userId='me', 
            q='in:inbox',
            maxResults=limit
        ).execute()
        
        messages = response.get('messages', [])
        
        if not messages:
            logger.info("Inbox is empty (according to API).")
            return

        print("-" * 120)
        print(f"{'ID':<18} | {'Labels':<30} | {'From':<40} | {'Subject'}")
        print("-" * 120)
        
        for msg in messages:
            details = client.service.users().messages().get(
                userId='me', 
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'From']
            ).execute()
            
            headers = details['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            labels = str(details.get('labelIds', []))[:30]
            
            # Truncate for display
            if len(sender) > 40: sender = sender[:37] + "..."
            if len(subject) > 30: subject = subject[:27] + "..."
            
            print(f"{msg['id']:<18} | {labels:<30} | {sender:<40} | {subject}")
            
        print("-" * 120)

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    debug_list_inbox()
