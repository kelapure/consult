"""Platform registry for routing emails to correct platform handler"""

from typing import Dict, Type, Optional
from loguru import logger

from .base import BasePlatform
from .glg_platform import GLGPlatform


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
        # Future: self.register('alphasights', AlphaSightsPlatform)
        # Future: self.register('guidepoint', GuidepointPlatform)
    
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
        
        # GLG detection
        if 'glg' in sender or 'glg' in subject or 'glg.it' in body:
            return 'glg'
        
        # AlphaSights detection
        if 'alphasights' in sender or 'alphasights' in subject:
            return 'alphasights'
        
        # Guidepoint detection
        if 'guidepoint' in sender or 'guidepoint' in subject:
            return 'guidepoint'
        
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

