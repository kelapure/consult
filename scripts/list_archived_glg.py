import os
import sys
import argparse
from dotenv import load_dotenv
from loguru import logger

# Add project root to path to allow imports from src
sys.path.append(os.getcwd())

from src.email.gmail_client import GmailClient

# Define GLG query (without in:inbox to find archived ones)
GLG_QUERY = 'from:glgroup.com'

def list_archived_glg_sample(limit=10):
    load_dotenv()
    
    try:
        client = GmailClient()
        if not client.authenticate():
            logger.error("Failed to authenticate")
            return

        # Search for emails NOT in INBOX (archived)
        full_query = f"-in:inbox {GLG_QUERY}"
        logger.info(f"Searching for recently archived emails: {full_query}")
        
        response = client.service.users().messages().list(
            userId='me', 
            q=full_query,
            maxResults=limit
        ).execute()
        
        messages = response.get('messages', [])
        
        if not messages:
            logger.info("No archived emails found matching query.")
            return

        logger.info(f"Found {len(messages)} archived emails. Listing details:")
        
        print("\nRecently Archived GLG Emails:")
        print("-" * 100)
        print(f"{ 'Date':<25} | {'Subject'}")
        print("-" * 100)
        
        for msg in messages:
            details = client.service.users().messages().get(
                userId='me', 
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'Date']
            ).execute()
            
            subject = next((h['value'] for h in details['payload']['headers'] if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in details['payload']['headers'] if h['name'] == 'Date'), 'Unknown Date')
            
            # Truncate subject for display
            if len(subject) > 70:
                subject = subject[:67] + "..."
                
            print(f"{date[:25]:<25} | {subject}")
            
        print("-" * 100)

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    list_archived_glg_sample()
