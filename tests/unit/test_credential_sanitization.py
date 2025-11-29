"""Unit tests for credential sanitization"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.sanitize import (
    sanitize_credentials,
    mask_password_in_logs,
    _sanitize_string,
    _sanitize_dict,
    _sanitize_list,
)


class TestCredentialSanitization:
    """Test credential and sensitive data sanitization"""

    def test_sanitize_password_in_json(self):
        """Test sanitizing password in JSON format"""
        text = '{"username": "user@example.com", "password": "secret123"}'
        sanitized = _sanitize_string(text)

        assert "secret123" not in sanitized
        assert "***REDACTED***" in sanitized
        assert "user@example.com" in sanitized  # Username should remain

    def test_sanitize_password_in_dict(self):
        """Test sanitizing password in dictionary"""
        data = {
            "username": "testuser",
            "password": "mysecretpassword",
            "email": "test@example.com"
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["username"] == "testuser"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["email"] == "test@example.com"

    def test_sanitize_api_key(self):
        """Test sanitizing API key"""
        data = {
            "api_key": "sk-1234567890abcdef",
            "name": "Test Service"
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["name"] == "Test Service"

    def test_sanitize_token(self):
        """Test sanitizing auth token"""
        data = {
            "auth_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "user_id": 123
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["auth_token"] == "***REDACTED***"
        assert sanitized["user_id"] == 123

    def test_sanitize_nested_dict(self):
        """Test sanitizing nested dictionaries"""
        data = {
            "user": {
                "username": "admin",
                "password": "adminpass"
            },
            "config": {
                "api_key": "secret-key-123"
            }
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["user"]["username"] == "admin"
        assert sanitized["user"]["password"] == "***REDACTED***"
        assert sanitized["config"]["api_key"] == "***REDACTED***"

    def test_sanitize_list_of_dicts(self):
        """Test sanitizing list of dictionaries"""
        data = [
            {"username": "user1", "password": "pass1"},
            {"username": "user2", "password": "pass2"}
        ]

        sanitized = _sanitize_list(data)

        assert sanitized[0]["username"] == "user1"
        assert sanitized[0]["password"] == "***REDACTED***"
        assert sanitized[1]["username"] == "user2"
        assert sanitized[1]["password"] == "***REDACTED***"

    def test_sanitize_password_url_format(self):
        """Test sanitizing password in URL format"""
        text = "Logging in with password=secretpass123&username=user"
        sanitized = _sanitize_string(text)

        assert "secretpass123" not in sanitized
        assert "password=***REDACTED***" in sanitized

    def test_sanitize_password_label_format(self):
        """Test sanitizing password with label format"""
        text = "Username: user@example.com, Password: MySecret123"
        sanitized = _sanitize_string(text)

        assert "MySecret123" not in sanitized
        assert "***REDACTED***" in sanitized
        assert "user@example.com" in sanitized  # Username preserved (in some form)

    def test_sanitize_mixed_sensitive_keys(self):
        """Test sanitizing various sensitive key names"""
        data = {
            "password": "pass1",
            "passwd": "pass2",
            "pwd": "pass3",
            "secret": "secret1",
            "secret_key": "secret2",
            "private_key": "private1",
            "normal_field": "normal_value"
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["passwd"] == "***REDACTED***"
        assert sanitized["pwd"] == "***REDACTED***"
        assert sanitized["secret"] == "***REDACTED***"
        assert sanitized["secret_key"] == "***REDACTED***"
        assert sanitized["private_key"] == "***REDACTED***"
        assert sanitized["normal_field"] == "normal_value"

    def test_sanitize_case_insensitive(self):
        """Test sanitization is case-insensitive"""
        data = {
            "PASSWORD": "pass1",
            "Password": "pass2",
            "API_KEY": "key1",
            "Api_Key": "key2"
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["PASSWORD"] == "***REDACTED***"
        assert sanitized["Password"] == "***REDACTED***"
        assert sanitized["API_KEY"] == "***REDACTED***"
        assert sanitized["Api_Key"] == "***REDACTED***"

    def test_sanitize_preserves_structure(self):
        """Test sanitization preserves data structure"""
        data = {
            "string": "value",
            "number": 123,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"}
        }

        sanitized = _sanitize_dict(data)

        assert isinstance(sanitized["string"], str)
        assert isinstance(sanitized["number"], int)
        assert isinstance(sanitized["boolean"], bool)
        assert sanitized["null"] is None
        assert isinstance(sanitized["list"], list)
        assert isinstance(sanitized["dict"], dict)

    def test_mask_password_in_logs(self):
        """Test masking passwords in log messages"""
        log_msg = 'User logged in with password="secretpass" successfully'
        masked = mask_password_in_logs(log_msg)

        assert "secretpass" not in masked
        assert "***REDACTED***" in masked

    def test_sanitize_credentials_wrapper_string(self):
        """Test sanitize_credentials wrapper with string"""
        text = '{"password": "secret"}'
        sanitized = sanitize_credentials(text)

        assert "secret" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_sanitize_credentials_wrapper_dict(self):
        """Test sanitize_credentials wrapper with dict"""
        data = {"password": "secret"}
        sanitized = sanitize_credentials(data)

        assert sanitized["password"] == "***REDACTED***"

    def test_sanitize_credentials_wrapper_list(self):
        """Test sanitize_credentials wrapper with list"""
        data = [{"password": "secret1"}, {"password": "secret2"}]
        sanitized = sanitize_credentials(data)

        assert sanitized[0]["password"] == "***REDACTED***"
        assert sanitized[1]["password"] == "***REDACTED***"

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string"""
        sanitized = _sanitize_string("")
        assert sanitized == ""

    def test_sanitize_none_value(self):
        """Test sanitizing None value"""
        sanitized = sanitize_credentials(None)
        assert sanitized is None

    def test_sanitize_with_hyphenated_keys(self):
        """Test sanitizing keys with hyphens"""
        data = {
            "api-key": "secret",
            "secret-token": "token123",
            "auth-password": "pass123"
        }

        sanitized = _sanitize_dict(data)

        assert sanitized["api-key"] == "***REDACTED***"
        assert sanitized["secret-token"] == "***REDACTED***"
        assert sanitized["auth-password"] == "***REDACTED***"

    def test_real_world_login_data(self):
        """Test with real-world login data structure"""
        login_data = {
            "username": "john.doe@company.com",
            "password": "MyP@ssw0rd!2024",
            "remember_me": True,
            "session_id": "abc-123-def-456"
        }

        sanitized = _sanitize_dict(login_data)

        assert sanitized["username"] == "john.doe@company.com"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["remember_me"] is True
        assert sanitized["session_id"] == "abc-123-def-456"
