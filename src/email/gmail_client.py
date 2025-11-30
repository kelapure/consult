"""Enhanced Gmail API client"""

import os
import pickle
import base64
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from loguru import logger
from bs4 import BeautifulSoup
import html2text
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class GmailClient:
    """Enhanced Gmail API client with classification and archiving"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    
    def __init__(self):
        """Initialize Gmail client"""
        self.email = os.getenv('GMAIL_EMAIL')
        if not self.email:
            raise ValueError("GMAIL_EMAIL environment variable not set")
        self.service = None
        self.processed_emails_file = 'logs/processed_emails.json'
        self.processed_emails = self._load_processed_emails()
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False  # Preserve links for URL extraction
        logger.info(f"Gmail client initialized for {self.email}")
    
    def _load_processed_emails(self) -> Set[str]:
        """Load previously processed email IDs"""
        try:
            if os.path.exists(self.processed_emails_file):
                with open(self.processed_emails_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_ids', []))
            return set()
        except Exception as e:
            logger.error(f"Error loading processed emails: {e}")
            return set()
    
    def _save_processed_email(self, email_id: str, action_taken: str):
        """Save processed email ID"""
        try:
            data = {'processed_ids': list(self.processed_emails)}
            if os.path.exists(self.processed_emails_file):
                with open(self.processed_emails_file, 'r') as f:
                    existing_data = json.load(f)
                    data['history'] = existing_data.get('history', [])
            else:
                data['history'] = []
            
            data['history'].append({
                'email_id': email_id,
                'action': action_taken,
                'timestamp': datetime.now().isoformat()
            })
            
            self.processed_emails.add(email_id)
            data['processed_ids'] = list(self.processed_emails)
            
            with open(self.processed_emails_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving processed email: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate with Gmail API using OAuth2 (cloud-friendly)"""
        try:
            creds = None
            
            # Try loading token from environment variable (base64 encoded)
            token_env = os.getenv('GMAIL_TOKEN_B64')
            if token_env:
                try:
                    token_data = base64.b64decode(token_env.encode())
                    creds = pickle.loads(token_data)
                    logger.info("Loaded token from environment variable")
                except Exception as e:
                    logger.warning(f"Failed to load token from env var: {e}")
            
            # Try loading token from Google Secret Manager
            if not creds:
                creds = self._load_token_from_secret_manager()
            
            # Fallback to local token.pickle (for development)
            if not creds and os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
                    logger.info("Loaded token from local file")
            
            # Validate and refresh credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired credentials...")
                    creds.refresh(Request())
                    # Save refreshed token
                    self._save_token(creds)
                else:
                    # Try to load credentials from environment or Secret Manager
                    creds = self._load_credentials_from_cloud()
                    
                    if not creds:
                        # Fallback to local OAuth flow (development only)
                        logger.info("Starting OAuth2 flow (local development)...")
                        
                        if not os.path.exists('credentials.json'):
                            logger.error("credentials.json not found and no cloud credentials available")
                            return False
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            'credentials.json', self.SCOPES)
                        creds = flow.run_local_server(port=0)
                        # Save token locally for development
                        self._save_token(creds, local_only=True)
            
            self.service = build('gmail', 'v1', credentials=creds)
            logger.success("Gmail authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
    
    def _load_token_from_secret_manager(self) -> Optional[Credentials]:
        """Load token from Google Secret Manager"""
        try:
            from google.cloud import secretmanager
            
            project_id = os.getenv('GCP_PROJECT_ID')
            secret_name = os.getenv('GMAIL_TOKEN_SECRET_NAME', 'gmail-token')
            
            if not project_id:
                return None
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            token_data = base64.b64decode(response.payload.data)
            creds = pickle.loads(token_data)
            logger.info("Loaded token from Secret Manager")
            return creds
        except ImportError:
            logger.debug("Secret Manager not available")
            return None
        except Exception as e:
            logger.debug(f"Failed to load token from Secret Manager: {e}")
            return None
    
    def _load_credentials_from_cloud(self) -> Optional[Credentials]:
        """Load credentials from environment or Secret Manager"""
        # Try environment variable (base64 encoded credentials.json)
        creds_env = os.getenv('GMAIL_CREDENTIALS_B64')
        if creds_env:
            try:
                creds_data = base64.b64decode(creds_env.encode())
                import json
                creds_dict = json.loads(creds_data.decode())
                creds = Credentials.from_authorized_user_info(creds_dict, self.SCOPES)
                logger.info("Loaded credentials from environment variable")
                return creds
            except Exception as e:
                logger.warning(f"Failed to load credentials from env var: {e}")
        
        # Try Secret Manager
        try:
            from google.cloud import secretmanager
            
            project_id = os.getenv('GCP_PROJECT_ID')
            secret_name = os.getenv('GMAIL_CREDENTIALS_SECRET_NAME', 'gmail-credentials')
            
            if not project_id:
                return None
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            creds_dict = json.loads(response.payload.data.decode())
            creds = Credentials.from_authorized_user_info(creds_dict, self.SCOPES)
            logger.info("Loaded credentials from Secret Manager")
            return creds
        except ImportError:
            logger.debug("Secret Manager not available")
            return None
        except Exception as e:
            logger.debug(f"Failed to load credentials from Secret Manager: {e}")
            return None
    
    def _save_token(self, creds: Credentials, local_only: bool = False):
        """Save token to appropriate location"""
        try:
            # In cloud environments, save to Secret Manager if configured
            if not local_only:
                project_id = os.getenv('GCP_PROJECT_ID')
                secret_name = os.getenv('GMAIL_TOKEN_SECRET_NAME', 'gmail-token')
                
                if project_id:
                    try:
                        from google.cloud import secretmanager
                        client = secretmanager.SecretManagerServiceClient()
                        token_data = pickle.dumps(creds)
                        token_b64 = base64.b64encode(token_data).decode()
                        
                        parent = f"projects/{project_id}"
                        try:
                            # Try to update existing secret
                            secret_path = f"{parent}/secrets/{secret_name}"
                            client.add_secret_version(
                                request={
                                    "parent": secret_path,
                                    "payload": {"data": token_b64.encode()}
                                }
                            )
                            logger.info("Saved token to Secret Manager")
                            return
                        except Exception:
                            # Secret doesn't exist, create it
                            logger.debug("Token secret doesn't exist, skipping cloud save")
                    except ImportError:
                        pass
            
            # Fallback to local file (development)
            if os.path.exists('token.pickle') or local_only:
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
                logger.debug("Saved token to local file")
        except Exception as e:
            logger.warning(f"Failed to save token: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def search_consultation_emails(self, days_back: int = 14) -> List[Dict]:
        """Search for consultation request emails"""
        try:
            logger.info(f"Searching for consultation emails from last {days_back} days")

            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

            # Search for emails from consultation platforms (GLG, Guidepoint)
            query = f'after:{start_date} (from:glgroup.com OR from:guidepointglobal.com OR from:guidepoint.com)'
            
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50  # Increased limit
            ).execute()
            
            messages = result.get('messages', [])
            
            emails = []
            for message in messages:
                email_data = self._get_email_details(message['id'])
                if email_data and email_data['id'] not in self.processed_emails:
                    emails.append(email_data)
            
            logger.info(f"Found {len(emails)} unprocessed consultation emails")
            return emails
            
        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            return []
        except Exception as e:
            logger.error(f"Email search failed: {e}")
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def _get_email_details(self, message_id: str) -> Optional[Dict]:
        """Get detailed email information"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload'].get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            sender_email = sender
            if '<' in sender and '>' in sender:
                sender_email = sender.split('<')[1].split('>')[0]
                sender = sender.split('<')[0].strip().strip('"')
            
            body_text = self._extract_body(message['payload'])
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'sender_email': sender_email,
                'date': date,
                'bodyText': body_text,
                'snippet': message.get('snippet', '')
            }
            
        except Exception as e:
            logger.error(f"Failed to get email details for {message_id}: {e}")
            return None
    
    def _extract_body(self, payload) -> str:
        """Extract email body text"""
        try:
            body = ""
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
                    elif part['mimeType'] == 'text/html':
                        data = part['body']['data']
                        html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                        body = self.h2t.handle(html_body)
                        break
            else:
                if payload['mimeType'] == 'text/plain':
                    data = payload['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                elif payload['mimeType'] == 'text/html':
                    data = payload['body']['data']
                    html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                    body = self.h2t.handle(html_body)
            
            return body
            
        except Exception as e:
            logger.error(f"Failed to extract email body: {e}")
            return ""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def archive_email(self, email_id: str):
        """Archive an email (remove from inbox)"""
        try:
            logger.info(f"Archiving email: {email_id}")
            
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            
            logger.success(f"Archived email: {email_id}")
            
        except Exception as e:
            logger.error(f"Failed to archive email {email_id}: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def unarchive_email(self, email_id: str):
        """Unarchive an email (add back to inbox)"""
        try:
            logger.info(f"Unarchiving email: {email_id}")

            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['INBOX']}
            ).execute()

            logger.success(f"Unarchived email: {email_id}")

        except Exception as e:
            logger.error(f"Failed to unarchive email {email_id}: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def send_reply(self, email_id: str, reply_text: str):
        """Send a reply to an email"""
        try:
            logger.info(f"Sending reply to email: {email_id}")
            
            original = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            headers = original['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            to_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
            
            if not subject.startswith('Re:'):
                subject = f"Re: {subject}"
            
            message = MIMEText(reply_text)
            message['to'] = to_email
            message['subject'] = subject
            message['In-Reply-To'] = email_id
            message['References'] = email_id
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.success("Reply sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def create_draft_reply(self, email_id: str, reply_text: str):
        """Create a draft reply to an email"""
        try:
            logger.info(f"Creating draft reply to email: {email_id}")

            original = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            headers = original['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            to_email = next((h['value'] for h in headers if h['name'] == 'From'), '')

            if not subject.startswith('Re:'):
                subject = f"Re: {subject}"

            message = MIMEText(reply_text)
            message['to'] = to_email
            message['subject'] = subject
            message['In-Reply-To'] = email_id
            message['References'] = email_id

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            self.service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw_message}}
            ).execute()

            logger.success("Draft reply created successfully")

        except Exception as e:
            logger.error(f"Failed to create draft reply: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True
    )
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None
    ):
        """
        Send a new email (not a reply)
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            attachments: Optional list of file paths to attach
        """
        try:
            logger.info(f"Sending email to {to_email}: {subject}")
            
            # Create message
            if attachments:
                # Multipart message with attachments
                message = MIMEMultipart()
                message['to'] = to_email
                message['subject'] = subject
                message['from'] = self.email
                
                # Add body
                message.attach(MIMEText(body, 'plain'))
                
                # Add attachments
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            message.attach(part)
                            logger.debug(f"Attached {file_path}")
            else:
                # Simple text message
                message = MIMEText(body)
                message['to'] = to_email
                message['subject'] = subject
                message['from'] = self.email
            
            # Encode and send
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.success(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise
    
    def mark_as_processed(self, email_id: str, action: str):
        """Mark email as processed"""
        self._save_processed_email(email_id, action)
        logger.info(f"Marked email {email_id} as processed: {action}")

