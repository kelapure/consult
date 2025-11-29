"""Metrics tracking"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from collections import defaultdict


class MetricsTracker:
    """Track metrics for analytics"""
    
    def __init__(self):
        """Initialize metrics tracker"""
        self.metrics = {
            'applications': 0,
            'acceptances': 0,
            'rejections': 0,
            'surveys': 0,
            'errors': 0,
            'by_platform': defaultdict(int),
            'by_strategy': defaultdict(int),
            'revenue_potential': 0.0,
            'response_times': [],
            'emails_processed': 0,
            'emails_archived': 0,
            'drafts_created': 0,
            'total_consultations': 0, # New metric to track all processed consultations
            'consultations': [],  # Detailed consultation log
            'failures': []  # Detailed failure log with reasons
        }
        logger.info("Metrics tracker initialized")
    
    def record_application(self, platform: str):
        """Record an application"""
        self.metrics['applications'] += 1
        self.metrics['by_platform'][platform] += 1
    
    def record_acceptance(self, platform: str, rate: float = 0.0):
        """Record an acceptance"""
        self.metrics['acceptances'] += 1
        self.metrics['by_platform'][platform] += 1
        if rate > 0:
            # Estimate revenue (assuming 40 hours/month)
            self.metrics['revenue_potential'] += rate * 40
    
    def record_rejection(self, platform: str):
        """Record a rejection"""
        self.metrics['rejections'] += 1

    def record_error(self, error_type: str):
        """Record an error"""
        self.metrics['errors'] += 1
    
    def record_failure(
        self,
        failure_type: str,
        component: str,
        reason: str,
        context: Dict[str, Any] = None
    ):
        """
        Record a detailed failure
        
        Args:
            failure_type: Type of failure (form_filling, authentication, api_call, etc.)
            component: Component that failed (glg_platform, claude_client, etc.)
            reason: Detailed reason for failure
            context: Additional context (email_id, platform, form_data keys, etc.)
        """
        self.metrics['failures'].append({
            'timestamp': datetime.now().isoformat(),
            'type': failure_type,
            'component': component,
            'reason': reason,
            'context': context or {}
        })
        self.metrics['errors'] += 1

    def record_email_processed(self):
        """Record an email processed"""
        self.metrics['emails_processed'] += 1
    
    def record_email_archived(self):
        """Record an email archived"""
        self.metrics['emails_archived'] += 1

    def record_draft_created(self):
        """Record an email draft created"""
        self.metrics['drafts_created'] += 1

    def record_consultation_processed(self):
        """Record that a consultation has been processed (accepted or declined)"""
        self.metrics['total_consultations'] += 1

    def record_consultation_detail(
        self,
        email_id: str,
        subject: str,
        platform: str,
        decision: str,
        reasoning: str,
        actions_taken: List[str]
    ):
        """Record detailed consultation information"""
        self.metrics['consultations'].append({
            'timestamp': datetime.now().isoformat(),
            'email_id': email_id,
            'subject': subject,
            'platform': platform,
            'decision': decision,
            'reasoning': reasoning[:200],  # Truncate
            'actions_taken': actions_taken
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        response_times = self.metrics['response_times']
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'total_applications': self.metrics['applications'],
            'total_acceptances': self.metrics['acceptances'],
            'total_rejections': self.metrics['rejections'],
            'total_surveys': self.metrics['surveys'],
            'total_errors': self.metrics['errors'],
            'acceptance_rate': (
                self.metrics['acceptances'] / self.metrics['applications']
                if self.metrics['applications'] > 0 else 0
            ),
            'by_platform': dict(self.metrics['by_platform']),
            'by_strategy': dict(self.metrics['by_strategy']),
            'revenue_potential': self.metrics['revenue_potential'],
            'avg_response_time_seconds': avg_response_time,
            'emails_processed': self.metrics['emails_processed'],
            'emails_archived': self.metrics['emails_archived'],
            'drafts_created': self.metrics['drafts_created'],
            'total_consultations': self.metrics['total_consultations'],
            'consultations': self.metrics['consultations'],
            'failures': self.metrics['failures']
        }
    
    def reset(self):
        """Reset metrics"""
        self.metrics = {
            'applications': 0,
            'acceptances': 0,
            'rejections': 0,
            'surveys': 0,
            'errors': 0,
            'by_platform': defaultdict(int),
            'by_strategy': defaultdict(int),
            'revenue_potential': 0.0,
            'response_times': [],
            'emails_processed': 0,
            'emails_archived': 0,
            'drafts_created': 0,
            'consultations': [],
            'failures': []
        }

