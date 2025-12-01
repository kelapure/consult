import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Add project root to path to allow imports from src
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

def debug_unarchive(email_id):
    load_dotenv()
    
    client = GmailClient()
    if not client.authenticate():
        logger.error("Failed to authenticate")
        return

    logger.info(f"Checking status of {email_id}...")
    
    try:
        # 1. Check if email exists and labels
        msg = client.service.users().messages().get(
            userId='me', 
            id=email_id,
            format='metadata',
            metadataHeaders=['Subject']
        ).execute()
        
        subject = next((h['value'] for h in msg['payload']['headers'] if h['name'] == 'Subject'), 'No Subject')
        labels = msg.get('labelIds', [])
        logger.info(f"Found email: {subject}")
        logger.info(f"Current Labels: {labels}")
        
        if 'INBOX' in labels:
            logger.warning(f"Email {email_id} is ALREADY in INBOX.")
            logger.info("No action needed for unarchive test.")
            return

        # 2. Attempt Unarchive
        logger.info(f"Attempting to unarchive {email_id}...")
        client.unarchive_email(email_id)
        
        # 3. Verify Unarchive
        logger.info("Verifying unarchive status...")
        msg_after = client.service.users().messages().get(
            userId='me', 
            id=email_id
        ).execute()
        
        new_labels = msg_after.get('labelIds', [])
        logger.info(f"New Labels: {new_labels}")
        
        if 'INBOX' in new_labels:
            logger.success(f"SUCCESS: Email {email_id} successfully unarchived (INBOX label restored).")
        else:
            logger.error(f"FAILURE: Email {email_id} still does NOT have INBOX label.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    # The ID of the Santa Clara Tax Receipt email
    target_id = "19ad71936b875902"
    debug_unarchive(target_id)
