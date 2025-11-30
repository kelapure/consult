"""Main email processor"""

from typing import List, Dict, Any, Optional
from loguru import logger

from .gmail_client import GmailClient
from .parser import EmailParser
from ..platforms.registry import PlatformRegistry
from ..memory.store import MemoryStore


class EmailProcessor:
    """Process consultation emails"""

    def __init__(self, memory_store: Optional[MemoryStore] = None):
        """
        Initialize email processor

        Args:
            memory_store: MemoryStore instance for tracking processed emails (uses local JSON storage)
        """
        self.gmail = GmailClient()
        self.parser = EmailParser()
        self.platform_registry = PlatformRegistry()
        self.memory_store = memory_store or MemoryStore()
        logger.info("Email processor initialized")
    
    async def list_recent_emails(self, days_back: int = 14) -> List[Dict[str, Any]]:
        """
        List recent consultation emails without processing them.
        
        This method returns raw email data for the agent to analyze and decide on.
        
        Args:
            days_back: Days to look back for emails
            
        Returns:
            List of email dictionaries with basic info and body text
        """
        # Authenticate
        if not self.gmail.authenticate():
            logger.error("Gmail authentication failed")
            return []
        
        # Search for emails
        emails = self.gmail.search_consultation_emails(days_back)
        if not emails:
            logger.info("No consultation emails found")
            return []
        
        # Enrich each email with platform detection
        result = []
        for email in emails:
            email_id = email.get('id')
            
            # Skip already processed emails
            if self.memory_store.is_processed(email_id):
                logger.debug(f"Skipping already processed email: {email.get('subject')}")
                continue
            
            # Detect platform
            platform = self.platform_registry.detect_platform(email)
            
            # Classify email type
            email_type = self.parser.classify_email_type(email)
            
            # Parse consultation details
            consultation_details = self.parser.parse_consultation_details(email)
            
            result.append({
                'id': email_id,
                'subject': email.get('subject'),
                'sender': email.get('sender'),
                'sender_email': email.get('sender_email'),
                'date': email.get('date'),
                'platform': platform,
                'email_type': email_type,
                'bodyText': email.get('bodyText', ''),
                'snippet': email.get('snippet', ''),
                'consultation_details': consultation_details,
            })
        
        logger.info(f"Found {len(result)} unprocessed consultation emails")
        return result
    
    async def process_emails(self, days_back: int = 14) -> List[Dict[str, Any]]:
        """
        Process consultation emails
        
        Args:
            days_back: Days to look back for emails
            
        Returns:
            List of processing results
        """
        # Authenticate
        if not self.gmail.authenticate():
            logger.error("Gmail authentication failed")
            return []
        
        # Search for emails
        emails = self.gmail.search_consultation_emails(days_back)
        if not emails:
            logger.info("No new consultation emails found")
            return []
        
        results = []
        skipped_count = 0
        
        for email in emails:
            try:
                email_id = email.get('id')
                
                # Check if already processed (checks local JSON storage)
                if self.memory_store.is_processed(email_id):
                    logger.info(f"Skipping already processed email: {email.get('subject')}")
                    skipped_count += 1
                    results.append({
                        'email_id': email_id,
                        'status': 'skipped',
                        'reason': 'already_processed'
                    })
                    continue
                
                result = await self._process_email(email)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing email {email.get('id')}: {e}")
                results.append({
                    'email_id': email.get('id'),
                    'status': 'error',
                    'error': str(e)
                })
        
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} already processed emails")
        
        return results
    
    async def _process_email(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single email"""
        email_id = email.get('id')
        logger.info(f"Processing email: {email.get('subject')}")
        
        # Classify email type
        email_type = self.parser.classify_email_type(email)
        logger.info(f"Email type: {email_type}")
        
        # Parse details
        consultation_details = self.parser.parse_consultation_details(email)
        consultation_details['email_id'] = email_id
        consultation_details['email_type'] = email_type
        
        # Detect platform
        platform = self.platform_registry.detect_platform(email)
        consultation_details['platform'] = platform
        
        result = {
            'email_id': email_id,
            'subject': email.get('subject'),
            'email_type': email_type,
            'platform': platform,
            'consultation_details': consultation_details,
            'status': 'processed'
        }

        # NOTE: mark_as_processed moved to record_consultation_decision tool
        # Only mark as processed AFTER Computer Use confirms submission (for accepts)
        # or AFTER draft email created (for declines)

        # NOTE: Archiving removed - agent will archive after making accept/decline decisions
        # and getting confirmation

        return result

