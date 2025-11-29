"""Base platform abstraction - data provider for Agent SDK

Platforms provide detection, extraction, and form templates.
The ConsultPipelineAgent handles all browser interaction via Computer Use.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger


class BasePlatform(ABC):
    """Abstract base class for consulting platforms (data providers only)"""

    def __init__(self, name: str):
        """
        Initialize platform

        Args:
            name: Platform name identifier
        """
        self.name = name
        logger.info(f"Initialized {name} platform")

    @abstractmethod
    async def prepare_application(self, consultation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare application form template for the agent

        Args:
            consultation_data: Parsed consultation details

        Returns:
            Form template dictionary with:
            - fields: Dict of field definitions (name -> {type, purpose})
            - context: Additional context for the agent to use when drafting content

        Note: The agent uses this template + CP writing style to draft actual content,
        then fills forms via Computer Use. This method provides structure, not content.
        """
        pass
