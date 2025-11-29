"""Credential and sensitive data sanitization utilities"""

import re
from typing import Dict, Any, Union, List


def sanitize_credentials(data: Union[str, Dict[str, Any], List]) -> Union[str, Dict[str, Any], List]:
    """
    Sanitize credentials and sensitive data from strings, dicts, or lists

    Args:
        data: String, dict, or list that may contain sensitive data

    Returns:
        Sanitized version with credentials masked
    """
    if isinstance(data, str):
        return _sanitize_string(data)
    elif isinstance(data, dict):
        return _sanitize_dict(data)
    elif isinstance(data, list):
        return _sanitize_list(data)
    else:
        return data


def _sanitize_string(text: str) -> str:
    """Sanitize sensitive data from strings"""
    if not text:
        return text

    # Mask common password patterns
    patterns = [
        # Password in JSON/dict format
        (r'"password"\s*:\s*"([^"]+)"', r'"password": "***REDACTED***"'),
        (r"'password'\s*:\s*'([^']+)'", r"'password': '***REDACTED***'"),

        # Password in key-value format
        (r'password=([^\s&]+)', r'password=***REDACTED***'),
        (r'Password:\s*(\S+)', r'Password: ***REDACTED***'),

        # API keys
        (r'(api[_-]?key|apikey)\s*[:=]\s*[\'"]*([a-zA-Z0-9_\-]+)[\'"]*',
         r'\1: ***REDACTED***'),

        # Tokens
        (r'(token|auth[_-]?token)\s*[:=]\s*[\'"]*([a-zA-Z0-9_\-\.]+)[\'"]*',
         r'\1: ***REDACTED***'),

        # Email + password combinations
        (r'(username|email)\s*[:=]\s*[\'"]*([^\s\'"]+)[\'"]*\s*,?\s*(password)\s*[:=]\s*[\'"]*([^\s\'"]+)[\'"]*',
         r'\1: "\2", \3: "***REDACTED***"'),
    ]

    sanitized = text
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive keys in dictionaries"""
    sensitive_keys = {
        'password', 'passwd', 'pwd',
        'api_key', 'apikey', 'api-key', 'apikey',
        'secret', 'secret_key', 'secret-key', 'secretkey',
        'token', 'auth_token', 'auth-token', 'authtoken',
        'access_token', 'refresh_token', 'accesstoken', 'refreshtoken',
        'private', 'privatekey', 'private_key', 'private-key',
    }

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower().replace('_', '').replace('-', '')

        # Check if key is sensitive
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        # Recursively sanitize nested structures
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = _sanitize_list(value)
        elif isinstance(value, str):
            sanitized[key] = _sanitize_string(value)
        else:
            sanitized[key] = value

    return sanitized


def _sanitize_list(data: List) -> List:
    """Sanitize sensitive data in lists"""
    sanitized = []
    for item in data:
        if isinstance(item, dict):
            sanitized.append(_sanitize_dict(item))
        elif isinstance(item, list):
            sanitized.append(_sanitize_list(item))
        elif isinstance(item, str):
            sanitized.append(_sanitize_string(item))
        else:
            sanitized.append(item)

    return sanitized


def mask_password_in_logs(log_message: str) -> str:
    """
    Mask passwords and sensitive data in log messages

    Args:
        log_message: Log message that may contain sensitive data

    Returns:
        Log message with sensitive data masked
    """
    return _sanitize_string(log_message)


def sanitize_screenshot_data(screenshot_data: bytes, replacements: Dict[str, str] = None) -> bytes:
    """
    Sanitize screenshot data by overlaying redaction boxes

    Note: This is a placeholder. Actual implementation would require image processing
    to detect and redact sensitive text in screenshots.

    Args:
        screenshot_data: Raw screenshot bytes
        replacements: Dict of text to find and replace coordinates

    Returns:
        Sanitized screenshot bytes (currently returns original - needs PIL/CV2)
    """
    # TODO: Implement image-based redaction using PIL or OpenCV
    # For now, return original (screenshot sanitization requires image processing)
    return screenshot_data
