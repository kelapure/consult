"""Platform registry for routing emails to correct platform handler"""

from typing import Dict, Type, Optional
from loguru import logger

from .base import BasePlatform
from .glg_platform import GLGPlatform
from .guidepoint_platform import GuidepointPlatform
from .coleman_platform import ColemanPlatform
from .office_hours_platform import OfficeHoursPlatform


class PlatformRegistry:
    """Registry for platform implementations"""
    
    def __init__(self):
        """Initialize platform registry"""
        self.platforms: Dict[str, Type[BasePlatform]] = {}
        self.platform_instances: Dict[str, BasePlatform] = {}
        self._register_defaults()
        logger.info("Platform registry initialized")
    
    def _register_defaults(self):
        """Register default platform implementations"""
        self.register('glg', GLGPlatform)
        self.register('guidepoint', GuidepointPlatform)
        self.register('coleman', ColemanPlatform)
        self.register('office_hours', OfficeHoursPlatform)
        # Future: self.register('alphasights', AlphaSightsPlatform)
    
    def register(self, name: str, platform_class: Type[BasePlatform]):
        """
        Register a platform implementation
        
        Args:
            name: Platform identifier
            platform_class: Platform class implementation
        """
        self.platforms[name] = platform_class
        logger.info(f"Registered platform: {name}")
    
    def detect_platform(self, email: Dict) -> Optional[str]:
        """
        Detect platform from email
        
        Args:
            email: Email dictionary
            
        Returns:
            Platform name or None
        """
        sender = email.get('sender_email', '').lower()
        subject = email.get('subject', '').lower()
        body = email.get('bodyText', '').lower()
        
        # Guidepoint detection - check FIRST since sender domain is most reliable
        # Emails from @guidepointglobal.com or @guidepoint.com
        if 'guidepoint' in sender or 'guidepoint' in subject:
            return 'guidepoint'

        # Coleman/VISASQ detection - check before other platforms
        # Emails from VISASQ/Coleman or containing coleman in subject
        if 'coleman' in sender or 'visasq' in sender:
            return 'coleman'
        if 'coleman' in subject or 'visasq' in subject:
            return 'coleman'

        # Office Hours detection - survey platform with Google OAuth
        # Emails from officehours.com or Kai Seed
        if 'officehours' in sender or 'office hours' in sender:
            return 'office_hours'
        if 'officehours.com' in body:
            return 'office_hours'
        if 'kai seed' in sender:
            return 'office_hours'

        # AlphaSights detection
        if 'alphasights' in sender or 'alphasights' in subject:
            return 'alphasights'

        # GLG detection - check last since 'glg' can appear in other email bodies
        if 'glgroup.com' in sender or 'glg.it' in sender or '@glg' in sender:
            return 'glg'
        if 'glg' in subject or 'glg.it' in body:
            return 'glg'

        return None
    
    def get_platform(self, name: str) -> Optional[BasePlatform]:
        """
        Get platform instance

        Args:
            name: Platform name (case-insensitive)

        Returns:
            Platform instance or None
        """
        # Normalize to lowercase for case-insensitive lookup
        name_lower = name.lower()

        if name_lower not in self.platforms:
            logger.warning(f"Platform {name} not registered")
            return None

        # Return cached instance or create new
        if name_lower not in self.platform_instances:
            platform_class = self.platforms[name_lower]
            self.platform_instances[name_lower] = platform_class()

        return self.platform_instances[name_lower]

