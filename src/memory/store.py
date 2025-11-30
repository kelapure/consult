"""Local JSON memory store"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger

from .models import ConsultationRecord


class MemoryStore:
    """Memory store for tracking processed consultations using local JSON storage"""

    def __init__(self):
        """Initialize memory store with local JSON storage"""
        self.local_store_file = 'memory_store.json'
        logger.info("Using local JSON storage for memory")
        self._load_local_store()

    def _load_local_store(self):
        """Load local JSON store"""
        try:
            if os.path.exists(self.local_store_file) and os.path.getsize(self.local_store_file) > 0:
                with open(self.local_store_file, 'r') as f:
                    self.local_data = json.load(f)
            else:
                self.local_data = {
                    'consultations': {},
                    'applications': {},
                    'telemetry': [],
                    'metrics': {}
                }
        except Exception as e:
            logger.error(f"Error loading local store: {e}")
            self.local_data = {
                'consultations': {},
                'applications': {},
                'telemetry': [],
                'metrics': {}
            }
        
        # Validate and migrate consultations data structure
        self._validate_consultations_structure()

    def _validate_consultations_structure(self):
        """Ensure consultations is a dict, not a list. Migrate if needed."""
        consultations = self.local_data.get('consultations')
        
        if not isinstance(consultations, dict):
            logger.warning(f"Converting consultations from {type(consultations).__name__} to dict")
            old_consultations = consultations if isinstance(consultations, list) else []
            self.local_data['consultations'] = {}
            
            # Migrate any existing list entries
            if isinstance(old_consultations, list):
                for item in old_consultations:
                    if isinstance(item, dict) and 'email_id' in item:
                        email_id = item['email_id']
                        self.local_data['consultations'][email_id] = item
                        logger.info(f"Migrated consultation: {email_id[:16]}...")
                    elif isinstance(item, dict):
                        logger.warning(f"Skipping list entry without email_id: {list(item.keys())[:3]}")
            
            self._save_local_store()
            logger.info(f"Migrated {len(self.local_data['consultations'])} consultations to dict format")

    def _save_local_store(self):
        """Save local JSON store"""
        try:
            with open(self.local_store_file, 'w') as f:
                json.dump(self.local_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving local store: {e}")

    def record_consultation(
        self,
        email_id: str,
        platform: str,
        subject: str,
        decision: str,
        reasoning: str,
        project_id: Optional[str] = None,
        submission_details: Optional[Dict[str, Any]] = None,
        application_submitted: bool = False
    ) -> bool:
        """Record a consultation decision with submission details"""
        try:
            # Ensure submission_details is always a dictionary
            if isinstance(submission_details, str):
                submission_details = {"message": submission_details}
            elif submission_details is None:
                submission_details = {}
            
            # Convert any datetime objects in submission_details to string representation
            for key, value in submission_details.items():
                if isinstance(value, datetime):
                    submission_details[key] = value.isoformat()

            record = ConsultationRecord(
                email_id=email_id,
                platform=platform,
                project_id=project_id,
                subject=subject,
                decision=decision,
                decision_reasoning=reasoning,
                submission_details=submission_details or {},
                application_submitted=application_submitted
            )

            self.local_data['consultations'][email_id] = record.dict()
            self._save_local_store()
            logger.info(f"📁 Saved consultation to local store: {subject[:50]}...")

            return True

        except Exception as e:
            logger.error(f"Error recording consultation: {e}")
            return False

    def is_processed(self, email_id: str) -> bool:
        """
        Check if email has been fully processed.
        
        An email is only considered processed when:
        - The opportunity was accepted AND
        - The application was successfully submitted on the platform
        
        Declined emails and accepted-but-not-submitted emails will be re-evaluated.
        """
        try:
            consultations = self.local_data.get('consultations', {})
            
            # Validate consultations is a dict
            if not isinstance(consultations, dict):
                logger.error(f"consultations is {type(consultations).__name__}, expected dict - running migration")
                self._validate_consultations_structure()
                consultations = self.local_data.get('consultations', {})
            
            consultation = consultations.get(email_id)
            if not isinstance(consultation, dict):
                return False
            
            # Only considered processed if accepted AND submitted on platform
            decision = consultation.get('decision', '')
            application_submitted = consultation.get('application_submitted', False)
            
            is_fully_processed = (decision == 'accept' and application_submitted)
            
            if is_fully_processed:
                logger.info(f"📁 Email {email_id[:16]}... already processed (accepted & submitted)")
            elif consultation:
                logger.info(f"📁 Email {email_id[:16]}... found but not fully processed (decision={decision}, submitted={application_submitted})")
            
            return is_fully_processed
        except Exception as e:
            logger.error(f"Error checking processed status: {e}")
            return False

    def get_consultation(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get consultation record"""
        try:
            consultations = self.local_data.get('consultations', {})
            if not isinstance(consultations, dict):
                logger.error(f"consultations is {type(consultations).__name__}, expected dict")
                self._validate_consultations_structure()
                consultations = self.local_data.get('consultations', {})
            return consultations.get(email_id)
        except Exception as e:
            logger.error(f"Error getting consultation: {e}")
            return None

    def get_recent_consultations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent consultation records

        Args:
            limit: Maximum number of records to retrieve

        Returns:
            List of consultation records, most recent first
        """
        try:
            # Sort by timestamp descending
            consultations = list(self.local_data['consultations'].values())
            consultations.sort(key=lambda x: x.get('processed_at', ''), reverse=True)
            return consultations[:limit]
        except Exception as e:
            logger.error(f"Error getting recent consultations: {e}")
            return []

    def save_run_metrics(self, run_id: str, metrics_data: Dict[str, Any]) -> bool:
        """
        Save metrics for a specific run

        Args:
            run_id: Unique run identifier (timestamp-based)
            metrics_data: Complete metrics dictionary

        Returns:
            True if successful
        """
        try:
            metrics_record = {
                'run_id': run_id,
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics_data
            }

            self.local_data['metrics'][run_id] = metrics_record
            self._save_local_store()
            logger.success(f"📁 Saved run metrics to local store (run: {run_id})")

            return True

        except Exception as e:
            logger.error(f"Error saving run metrics: {e}")
            return False

    def get_run_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific run"""
        try:
            return self.local_data['metrics'].get(run_id)
        except Exception as e:
            logger.error(f"Error getting run metrics: {e}")
            return None

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent run metrics

        Args:
            limit: Maximum number of runs to retrieve

        Returns:
            List of run metrics, most recent first
        """
        try:
            # Sort by timestamp descending
            runs = list(self.local_data['metrics'].values())
            runs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return runs[:limit]
        except Exception as e:
            logger.error(f"Error getting recent runs: {e}")
            return []

    def get_aggregated_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get aggregated metrics for the last N days

        Args:
            days: Number of days to aggregate

        Returns:
            Aggregated metrics dictionary
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            runs = [
                run for run in self.local_data['metrics'].values()
                if datetime.fromisoformat(run['timestamp']) >= cutoff_date
            ]

            # Aggregate metrics
            aggregated = {
                'total_runs': len(runs),
                'date_range': f"Last {days} days",
                'total_emails_processed': 0,
                'total_emails_archived': 0,
                'total_emails_replied': 0,
                'total_applications': 0,
                'total_acceptances': 0,
                'total_rejections': 0,
                'total_errors': 0,
                'total_failures': 0,
                'by_platform': {},
                'failure_types': {},
                'failures_by_component_reason': {},
                'runs': runs
            }

            for run in runs:
                metrics = run.get('metrics', {})
                aggregated['total_emails_processed'] += metrics.get('emails_processed', 0)
                aggregated['total_emails_archived'] += metrics.get('emails_archived', 0)
                aggregated['total_emails_replied'] += metrics.get('emails_replied', 0)
                aggregated['total_applications'] += metrics.get('applications', 0)
                aggregated['total_acceptances'] += metrics.get('acceptances', 0)
                aggregated['total_rejections'] += metrics.get('rejections', 0)
                aggregated['total_errors'] += metrics.get('errors', 0)

                # Aggregate platforms
                for platform, count in metrics.get('by_platform', {}).items():
                    aggregated['by_platform'][platform] = aggregated['by_platform'].get(platform, 0) + count

                # Aggregate failures by component and reason
                for failure in metrics.get('failures', []):
                    component = failure.get('component', 'unknown')
                    reason = failure.get('reason', 'unknown')
                    if component not in aggregated['failures_by_component_reason']:
                        aggregated['failures_by_component_reason'][component] = {}
                    aggregated['failures_by_component_reason'][component][reason] = \
                        aggregated['failures_by_component_reason'][component].get(reason, 0) + 1
                aggregated['total_failures'] += len(metrics.get('failures', []))

            return aggregated

        except Exception as e:
            logger.error(f"Error getting aggregated metrics: {e}")
            return {}

    def get_aggregated_metrics_by_consultation(
        self,
        start_date: datetime,
        end_date: datetime,
        platform_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics from consultation records for a specific date range and optional platform filter.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            platform_filter: Optional platform name to filter by.

        Returns:
            Aggregated metrics dictionary based on filtered consultations.
        """
        try:
            filtered_consultations = []
            for email_id, consultation in self.local_data['consultations'].items():
                processed_at_str = consultation.get('processed_at')
                if not isinstance(processed_at_str, str) or not processed_at_str:
                    logger.warning(f"Skipping consultation {email_id} due to invalid or missing 'processed_at' timestamp: {processed_at_str}")
                    continue

                try:
                    processed_at = datetime.fromisoformat(processed_at_str)
                except ValueError as ve:
                    logger.warning(f"Skipping consultation {email_id} due to malformed 'processed_at' timestamp '{processed_at_str}': {ve}")
                    continue
                
                # Apply date range filter
                if not (start_date <= processed_at <= end_date + timedelta(days=1)):
                    continue

                # Apply platform filter
                if platform_filter and consultation.get('platform', '').lower() != platform_filter.lower():
                    continue
                
                filtered_consultations.append(consultation)
            
            # Aggregate metrics from filtered consultations
            aggregated = {
                'total_consultations': len(filtered_consultations), 
                'total_emails_processed': 0,
                'total_emails_archived': 0,
                'total_drafts_created': 0, 
                'total_applications': 0,
                'total_acceptances': 0,
                'total_rejections': 0,
                'total_surveys': 0,
                'total_errors': 0,
                'total_failures': 0,
                'by_platform': {},
                'by_strategy': {},
                'revenue_potential': 0.0,
                'avg_response_time_seconds': 0.0,
                'consultations': filtered_consultations, 
                'failures_by_component_reason': {}
            }
            
            total_response_time = 0.0
            response_time_count = 0

            for consultation in filtered_consultations:
                aggregated['total_emails_processed'] += 1 
                
                # Decisions
                decision = consultation.get('decision')
                if decision == 'accept':
                    aggregated['total_acceptances'] += 1
                    if consultation.get('application_submitted'):
                        aggregated['total_applications'] += 1
                        platform = consultation.get('platform', 'unknown')
                        aggregated['by_platform'][platform] = aggregated['by_platform'].get(platform, 0) + 1
                        
                        # Revenue potential (if available in submission_details)
                        submission_details = consultation.get('submission_details', {})
                        rate_info = submission_details.get('rate')
                        if isinstance(rate_info, (int, float)):
                            aggregated['revenue_potential'] += rate_info * 40 # Assuming 40 hours/month
                elif decision == 'decline':
                    aggregated['total_rejections'] += 1

                # Errors/Failures (from submission_details if application was attempted)
                submission_details = consultation.get('submission_details', {})
                if submission_details.get('success') is False:
                    aggregated['total_errors'] += 1
                    aggregated['total_failures'] += 1
                    component = submission_details.get('component', 'browser_automation')
                    reason = submission_details.get('error', 'unknown_failure')
                    
                    if component not in aggregated['failures_by_component_reason']:
                        aggregated['failures_by_component_reason'][component] = {}
                    aggregated['failures_by_component_reason'][component][reason] = \
                        aggregated['failures_by_component_reason'][component].get(reason, 0) + 1
                
                # Response times (if available in submission_details)
                
                execution_time = submission_details.get('execution_time_seconds')
                if isinstance(execution_time, (int, float)):
                    total_response_time += execution_time
                    response_time_count += 1
            
            if response_time_count > 0:
                aggregated['avg_response_time_seconds'] = total_response_time / response_time_count

            if aggregated['total_applications'] > 0:
                aggregated['acceptance_rate'] = (aggregated['total_acceptances'] / aggregated['total_applications'])
            else:
                aggregated['acceptance_rate'] = 0.0

            return aggregated

        except Exception as e:
            logger.error(f"Error getting aggregated metrics by consultation: {e}")
            return {}