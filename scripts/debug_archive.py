import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Add project root to path to allow imports from src
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

def debug_archive(email_id):
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
        
        if 'INBOX' not in labels:
            logger.warning(f"Email {email_id} is ALREADY archived (not in INBOX).")
            # If it's not in inbox, let's put it BACK in inbox to test archiving
            logger.info("Moving BACK to INBOX for test...")
            client.unarchive_email(email_id)
            
            # Verify it's back
            msg = client.service.users().messages().get(userId='me', id=email_id).execute()
            if 'INBOX' in msg.get('labelIds', []):
                 logger.success("Successfully restored to INBOX. Now testing archive...")
            else:
                 logger.error("Failed to restore to INBOX. Aborting.")
                 return

        # 2. Attempt Archive
        logger.info(f"Attempting to archive {email_id}...")
        client.archive_email(email_id)
        
        # 3. Verify Archive
        logger.info("Verifying archive status...")
        msg_after = client.service.users().messages().get(
            userId='me', 
            id=email_id
        ).execute()
        
        new_labels = msg_after.get('labelIds', [])
        logger.info(f"New Labels: {new_labels}")
        
        if 'INBOX' not in new_labels:
            logger.success(f"SUCCESS: Email {email_id} successfully archived (removed from INBOX).")
        else:
            logger.error(f"FAILURE: Email {email_id} still has INBOX label.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    # The ID picked from the previous list command
    target_id = "19ad71936b875902"
    debug_archive(target_id)
