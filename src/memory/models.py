"""Data models for memory store"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field


class ConsultationRecord(BaseModel):
    """Consultation record model"""
    email_id: str
    platform: str
    project_id: Optional[str] = None
    subject: str
    decision: str  # 'accept', 'decline'
    decision_reasoning: str
    submission_details: Optional[Union[Dict[str, Any], str]] = None  # Form inputs/answers or status message
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    application_submitted: bool = False
    application_id: Optional[str] = None


class ApplicationRecord(BaseModel):
    """Application record model"""
    consultation_id: str
    platform: str
    project_id: str
    submitted_at: datetime = Field(default_factory=datetime.now)
    form_strategy: str  # Which form filling strategy was used
    status: str = 'submitted'  # 'submitted', 'accepted', 'rejected', 'pending'
    confirmation_received: bool = False


class StrategyTelemetry(BaseModel):
    """Form filling strategy telemetry"""
    platform: str
    strategy: str
    success: bool
    filled_fields: int
    total_fields: int
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

