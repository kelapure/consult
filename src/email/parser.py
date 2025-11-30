"""Email parsing and classification"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class ConsultationDetails(BaseModel):
    """Validated consultation details model"""
    subject: str = Field(default="", min_length=0)
    sender: str = Field(default="", min_length=0)
    sender_email: str = Field(default="", min_length=0)
    timestamp: str = Field(default="")
    skills_required: List[str] = Field(default_factory=list)
    duration: str = Field(default="")
    budget: str = Field(default="")
    start_date: str = Field(default="")
    project_description: str = Field(default="")
    project_url: Optional[str] = None
    project_id: Optional[str] = None
    email_id: Optional[str] = None
    email_type: Optional[str] = None
    platform: Optional[str] = None
    
    @field_validator('skills_required')
    @classmethod
    def validate_skills(cls, v):
        """Ensure skills are strings"""
        return [str(skill) for skill in v if skill]


class EmailParser:
    """Parse and classify consultation emails"""
    
    def __init__(self):
        """Initialize email parser"""
        logger.info("Email parser initialized")
    
    def parse_consultation_details(self, email_content: Dict) -> Dict[str, Any]:
        """Parse consultation details from email content with validation"""
        try:
            # Parse raw details
            details = {
                'subject': email_content.get('subject', ''),
                'sender': email_content.get('sender', ''),
                'sender_email': email_content.get('sender_email', ''),
                'timestamp': email_content.get('date', ''),
                'skills_required': [],
                'duration': '',
                'budget': '',
                'start_date': '',
                'project_description': '',
                'project_url': None,
                'project_id': None
            }
            
            body_text = email_content.get('bodyText', '').lower()
            body_original = email_content.get('bodyText', '')
            
            # Extract skills
            skill_keywords = [
                'python', 'java', 'javascript', 'react', 'node.js', 'typescript',
                'aws', 'gcp', 'azure', 'google cloud', 'cloud computing',
                'docker', 'kubernetes', 'k8s', 'container',
                'machine learning', 'ai', 'artificial intelligence', 'llm', 'ml',
                'microservices', 'api', 'rest', 'graphql',
                'postgresql', 'mongodb', 'redis', 'database',
                'agile', 'scrum', 'devops', 'ci/cd'
            ]
            
            for skill in skill_keywords:
                if skill in body_text:
                    details['skills_required'].append(skill)
            
            # Extract duration
            duration_match = re.search(r'(\d+)\s*(month|week|day|hour)', body_text)
            if duration_match:
                details['duration'] = duration_match.group(0)
            
            # Extract budget
            budget_patterns = [
                r'\$[\d,]+(?:-\$?[\d,]+)?\s*(?:per\s*)?(?:hour|hr|hourly)',
                r'\$[\d,]+(?:-\$?[\d,]+)?\s*(?:USD|usd)?',
                r'budget[:\s]+\$?[\d,]+'
            ]
            for pattern in budget_patterns:
                budget_match = re.search(pattern, body_original, re.IGNORECASE)
                if budget_match:
                    details['budget'] = budget_match.group(0)
                    break
            
            # Extract start date
            start_patterns = [
                r'start\s*(?:date)?:?\s*([A-Za-z]+ \d{4}|\d{1,2}/\d{1,2}/\d{4})',
                r'beginning?\s*(?:on|date)?:?\s*([A-Za-z]+ \d{4}|\d{1,2}/\d{1,2}/\d{4})'
            ]
            for pattern in start_patterns:
                start_match = re.search(pattern, body_original, re.IGNORECASE)
                if start_match:
                    details['start_date'] = start_match.group(1)
                    break
            
            # Extract project URL with platform-aware logic
            url_pattern = r'https?://[^\s<>"\])]+'
            urls = re.findall(url_pattern, body_original)
            subject = email_content.get('subject', '')
            sender_email = email_content.get('sender_email', '')
            
            # Check if this is a Guidepoint email
            is_guidepoint = 'guidepoint' in sender_email.lower() or 'guidepoint' in subject.lower()

            # Check if this is a Coleman/VISASQ email
            is_coleman = ('coleman' in sender_email.lower() or 'visasq' in sender_email.lower() or
                         'coleman' in subject.lower() or 'visasq' in subject.lower())

            # Check if this is an Office Hours email (survey platform with Google OAuth)
            is_office_hours = ('officehours' in sender_email.lower() or 'office hours' in sender_email.lower() or
                              'kai seed' in sender_email.lower() or 'officehours.com' in body_text)

            # For Office Hours emails, use home URL (surveys accessible from dashboard)
            if is_office_hours:
                details['project_url'] = "https://officehours.com/home"
                details['platform'] = 'office_hours'
                # Try to extract survey topic from subject
                topic_match = re.search(r'(?:Survey|Complete|Paid)[\s:]+(.+?)(?:\s*-|$)', subject, re.IGNORECASE)
                if topic_match:
                    details['project_id'] = topic_match.group(1).strip()[:50]
                logger.info(f"Office Hours email: using home URL, survey topic: {details.get('project_id', 'N/A')}")

            # For Coleman emails, use dashboard URL (projects are accessed from dashboard)
            elif is_coleman:
                # Coleman uses a dashboard-based workflow - all projects listed at to-do URL
                details['project_url'] = "https://experts.coleman.colemanerm.com/#!/expert/to-do"
                # Try to extract project title from subject for reference
                # Subject pattern: "Following-up on New Request from VISASQ/Coleman: {Title}"
                title_match = re.search(r'(?:from\s+)?(?:VISASQ/)?Coleman[:\s]+(.+?)(?:\s*-|$)', subject, re.IGNORECASE)
                if title_match:
                    details['project_id'] = title_match.group(1).strip()[:50]  # Use title as ID
                logger.info(f"Coleman email: using dashboard URL, project reference: {details.get('project_id', 'N/A')}")

            # For Guidepoint emails, extract project ID from subject and construct direct URL
            elif is_guidepoint:
                # Extract project ID from subject (e.g., "(#1647050)" or "#1645979")
                project_id_match = re.search(r'#(\d{6,8})', subject)
                if project_id_match:
                    project_id = project_id_match.group(1)
                    details['project_id'] = project_id
                    # Construct direct form URL
                    details['project_url'] = f"https://new.guidepointglobaladvisors.com/requests/response/{project_id}"
                    logger.info(f"Guidepoint email: extracted project ID {project_id}, URL: {details['project_url']}")
                else:
                    # Fallback: try to find guidepointglobaladvisors URLs in body
                    guidepoint_urls = [u for u in urls if 'guidepointglobaladvisors.com/requests' in u]
                    if guidepoint_urls:
                        details['project_url'] = guidepoint_urls[0]
                        pid_match = re.search(r'/response/(\d+)', guidepoint_urls[0])
                        if pid_match:
                            details['project_id'] = pid_match.group(1)
                    else:
                        # Use dashboard URL as fallback
                        details['project_url'] = "https://new.guidepointglobaladvisors.com/requests"
                        logger.warning(f"Guidepoint email without project ID in subject: {subject}")
            else:
                # For GLG and other platforms
                glg_urls = [u for u in urls if 'members.glgresearch.com/accept' in u or 'glg.it' in u]
                
                if glg_urls:
                    details['project_url'] = glg_urls[0]
                    # Try to extract project ID from GLG URL
                    project_id_match = re.search(r'/projects?/([^/?]+)', glg_urls[0])
                    if project_id_match:
                        details['project_id'] = project_id_match.group(1)
                elif urls:
                    # Filter out image/tracking URLs
                    valid_urls = [u for u in urls if not any(x in u.lower() for x in 
                        ['static-crm', '/images/', '.png', '.jpg', '.gif', 'wf/open', 'url2375'])]
                    if valid_urls:
                        details['project_url'] = valid_urls[0]
                        project_id_match = re.search(r'/projects?/([^/?]+)', valid_urls[0])
                        if project_id_match:
                            details['project_id'] = project_id_match.group(1)
                    elif urls:
                        details['project_url'] = urls[0]
            
            # Get project description (first paragraph)
            paragraphs = body_original.split('\n\n')
            if paragraphs:
                details['project_description'] = paragraphs[0][:500]
            
            # Validate and return using Pydantic model
            try:
                validated_details = ConsultationDetails(**details)
                return validated_details.model_dump()
            except Exception as validation_error:
                logger.warning(f"Validation error, returning raw details: {validation_error}")
                return details
            
        except Exception as e:
            logger.error(f"Error parsing consultation details: {e}", exc_info=True)
            return {}
    
    def classify_email_type(self, email: Dict[str, Any]) -> str:
        """
        Classify email type
        
        Returns:
            'consultation_invitation', 'survey', 'follow_up', 'other'
        """
        subject = email.get('subject', '').lower()
        body = email.get('bodyText', '').lower()
        text = f"{subject} {body}"
        
        # Survey patterns
        survey_patterns = [
            'survey', 'questionnaire', 'complete this form', 'fill out',
            'take this survey', 'your feedback'
        ]
        for pattern in survey_patterns:
            if pattern in text:
                return 'survey'
        
        # Consultation invitation patterns
        invitation_patterns = [
            'consultation', 'consulting opportunity', 'project opportunity',
            'we think you', 'review project', 'accept opportunity',
            'apply now', 'interested in'
        ]
        for pattern in invitation_patterns:
            if pattern in text:
                return 'consultation_invitation'
        
        # Follow-up patterns
        followup_patterns = [
            'follow up', 'follow-up', 'reminder', 'still interested',
            'haven\'t heard', 'checking in'
        ]
        for pattern in followup_patterns:
            if pattern in text:
                return 'follow_up'
        
        return 'other'

