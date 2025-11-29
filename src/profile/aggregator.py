"""Profile aggregator from multiple sources"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import yaml


class ProfileAggregator:
    """Aggregate profile data from all sources"""
    
    def __init__(
        self,
        json_profile_path: Optional[str] = None,
        config_path: str = 'config/config.yaml',
        cache_ttl_hours: int = 24
    ):
        """
        Initialize profile aggregator
        
        Args:
            json_profile_path: Path to comprehensive JSON profile
            config_path: Path to config.yaml
            cache_ttl_hours: Cache TTL in hours
        """
        # Use environment variable or provided path, but don't hardcode user-specific paths
        default_profile = os.getenv('PROFILE_JSON_PATH', 'profiles/rohit_kelapure_comprehensive_profile.json')
        self.json_profile_path = json_profile_path or default_profile
        self.config_path = config_path
        self.cache_ttl_hours = cache_ttl_hours
        self.cache_file = '.profile_cache.json'
        
        logger.info("Profile aggregator initialized")
    
    async def aggregate(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Aggregate profile from all sources
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Unified profile dictionary
        """
        # Check cache first
        if not force_refresh:
            cached_profile = self._load_cache()
            if cached_profile:
                logger.info("Using cached profile")
                return cached_profile
        
        logger.info("Aggregating profile from local sources...")
        
        # Start with JSON profile (most comprehensive) from profiles directory
        profile = self._load_json_profile()
        
        # Load config.yaml for additional settings
        config_profile = self._load_config_profile()
        
        # Merge config into profile
        profile = self._merge_profiles(profile, config_profile)
        
        # Generate summary
        profile['summary'] = self._generate_summary(profile)
        profile['aggregated_at'] = datetime.now().isoformat()
        
        # Save to cache
        self._save_cache(profile)
        
        logger.success("Profile aggregation complete")
        return profile
    
    def _load_json_profile(self) -> Dict[str, Any]:
        """Load comprehensive JSON profile"""
        try:
            if os.path.exists(self.json_profile_path):
                with open(self.json_profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"JSON profile not found at {self.json_profile_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading JSON profile: {e}")
            return {}
    
    def _load_config_profile(self) -> Dict[str, Any]:
        """Load profile from config.yaml"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    return config.get('profile', {})
            return {}
        except Exception as e:
            logger.error(f"Error loading config profile: {e}")
            return {}
    
    def _merge_profiles(self, base: Dict[str, Any], additional: Dict[str, Any]) -> Dict[str, Any]:
        """Merge additional profile data into base"""
        merged = base.copy()
        
        for key, value in additional.items():
            if key in merged:
                # Merge lists
                if isinstance(merged[key], list) and isinstance(value, list):
                    # Only deduplicate if items are hashable (strings, numbers)
                    # For dicts/objects, just concatenate
                    try:
                        merged[key] = list(set(merged[key] + value))
                    except TypeError:
                        # Contains unhashable types (dicts, lists), just concatenate
                        merged[key] = merged[key] + value
                # Merge dicts recursively
                elif isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = self._merge_profiles(merged[key], value)
                # Overwrite with new value
                else:
                    merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    def _generate_summary(self, profile: Dict[str, Any]) -> str:
        """Generate text summary of profile for LLM consumption"""
        parts = []
        
        # Basic info
        name = profile.get('personalInfo', {}).get('name') or profile.get('name', 'Consultant')
        years_exp = profile.get('professionalSummary', {}).get('yearsOfExperience', {}).get('total') or profile.get('years_experience', 20)
        current_role = profile.get('professionalSummary', {}).get('currentRole') or profile.get('role', 'Consultant')
        
        parts.append(f"{name} is a {current_role} with {years_exp} years of experience.")
        
        # Key highlights
        highlights = profile.get('professionalSummary', {}).get('keyHighlights', [])
        if highlights:
            parts.append(f"Key achievements: {', '.join(highlights[:3])}")
        
        # Skills
        skills_data = profile.get('skills', {})
        if isinstance(skills_data, dict):
            skills = skills_data.get('technical', []) or skills_data.get('skills', [])
        elif isinstance(skills_data, list):
            skills = skills_data
        else:
            skills = []
        
        if isinstance(skills, list) and skills:
            # Filter out non-string items
            skill_strings = [str(s) for s in skills[:10] if s]
            if skill_strings:
                parts.append(f"Technical expertise: {', '.join(skill_strings)}")
        
        # Experience summary
        experience = profile.get('experience', [])
        if experience and isinstance(experience, list):
            recent_roles = experience[:2]
            role_summaries = []
            for r in recent_roles:
                if isinstance(r, dict):
                    role_summaries.append(f"{r.get('role', '')} at {r.get('company', '')}")
                elif isinstance(r, str):
                    role_summaries.append(r)
            if role_summaries:
                parts.append(f"Recent roles: {', '.join(role_summaries)}")
        
        # Patents
        patents = profile.get('patents', {})
        if patents:
            total = patents.get('total', 0)
            if total > 0:
                parts.append(f"Has {total} patents in enterprise software.")
        
        return " ".join(parts)
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached profile if still valid"""
        try:
            if not os.path.exists(self.cache_file):
                return None
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check TTL
            cached_at = datetime.fromisoformat(cache_data.get('aggregated_at', ''))
            age = datetime.now() - cached_at
            
            if age < timedelta(hours=self.cache_ttl_hours):
                return cache_data.get('profile')
            else:
                logger.info("Cache expired, refreshing profile")
                return None
                
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            return None
    
    def _save_cache(self, profile: Dict[str, Any]):
        """Save profile to cache"""
        try:
            cache_data = {
                'profile': profile,
                'aggregated_at': profile.get('aggregated_at', datetime.now().isoformat())
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.debug("Profile cached")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")

