"""Unit tests for cookie detection logic"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.browser.cookie_detection import (
    COOKIE_BANNER_SELECTORS,
    ACCEPT_BUTTON_SELECTORS,
    get_cookie_banner_priority,
    is_cookie_related_selector,
)


class TestCookieDetection:
    """Test cookie banner detection logic"""

    def test_cookie_banner_selectors_list_exists(self):
        """Test that cookie banner selectors list is defined"""
        assert COOKIE_BANNER_SELECTORS is not None
        assert isinstance(COOKIE_BANNER_SELECTORS, list)
        assert len(COOKIE_BANNER_SELECTORS) > 0

    def test_cookie_banner_selectors_include_common_ids(self):
        """Test that common ID selectors are included"""
        selectors_str = ' '.join(COOKIE_BANNER_SELECTORS)

        # Common cookie banner IDs
        assert '#cookie-banner' in COOKIE_BANNER_SELECTORS
        assert '#cookie-consent' in COOKIE_BANNER_SELECTORS
        assert '#cookieConsent' in COOKIE_BANNER_SELECTORS or '#cookieconsent' in COOKIE_BANNER_SELECTORS

    def test_cookie_banner_selectors_include_common_classes(self):
        """Test that common class selectors are included"""
        selectors_str = ' '.join(COOKIE_BANNER_SELECTORS)

        # Common class names
        assert '.cookie-banner' in COOKIE_BANNER_SELECTORS
        assert '.cookie-consent' in COOKIE_BANNER_SELECTORS
        assert 'consent-banner' in selectors_str

    def test_cookie_banner_selectors_include_third_party(self):
        """Test that third-party cookie solutions are included"""
        selectors_str = ' '.join(COOKIE_BANNER_SELECTORS)

        # OneTrust
        assert 'onetrust' in selectors_str.lower()

        # Cookiebot
        assert 'cookiebot' in selectors_str.lower()

    def test_accept_button_selectors_list_exists(self):
        """Test that accept button selectors list is defined"""
        assert ACCEPT_BUTTON_SELECTORS is not None
        assert isinstance(ACCEPT_BUTTON_SELECTORS, list)
        assert len(ACCEPT_BUTTON_SELECTORS) > 0

    def test_accept_button_selectors_include_common_ids(self):
        """Test that common accept button IDs are included"""
        selectors_str = ' '.join(ACCEPT_BUTTON_SELECTORS)

        assert '#accept-cookies' in ACCEPT_BUTTON_SELECTORS or 'accept-cookies' in selectors_str
        assert 'acceptCookies' in selectors_str

    def test_accept_button_selectors_include_text_matching(self):
        """Test that text-based button selectors are included"""
        selectors_str = ' '.join(ACCEPT_BUTTON_SELECTORS)

        # Common button texts
        assert 'Accept' in selectors_str
        assert 'Accept All' in selectors_str or 'accept-all' in selectors_str.lower()
        assert 'I Accept' in selectors_str or 'I Agree' in selectors_str

    def test_cookie_banner_priority_id_first(self):
        """Test that ID selectors have higher priority than classes"""
        id_selector = '#cookie-banner'
        class_selector = '.cookie-banner'

        id_priority = get_cookie_banner_priority(id_selector)
        class_priority = get_cookie_banner_priority(class_selector)

        # Lower number = higher priority
        assert id_priority < class_priority

    def test_cookie_banner_priority_known_selector(self):
        """Test priority for known selectors"""
        priority = get_cookie_banner_priority('#cookie-banner')

        # Should be a valid index (not 999)
        assert priority < 999
        assert priority >= 0

    def test_cookie_banner_priority_unknown_selector(self):
        """Test priority for unknown selectors"""
        priority = get_cookie_banner_priority('#completely-unknown-selector-xyz')

        # Unknown selectors get lowest priority
        assert priority == 999

    def test_is_cookie_related_selector_cookie_keyword(self):
        """Test detection of cookie-related selectors"""
        assert is_cookie_related_selector('#cookie-banner')
        assert is_cookie_related_selector('.cookie-consent')
        assert is_cookie_related_selector('[data-cookie-notice]')

    def test_is_cookie_related_selector_consent_keyword(self):
        """Test detection with consent keyword"""
        assert is_cookie_related_selector('#consent-banner')
        assert is_cookie_related_selector('.consent-dialog')

    def test_is_cookie_related_selector_privacy_keyword(self):
        """Test detection with privacy keyword"""
        assert is_cookie_related_selector('#privacy-notice')
        assert is_cookie_related_selector('.privacy-banner')

    def test_is_cookie_related_selector_gdpr_keyword(self):
        """Test detection with GDPR keyword"""
        assert is_cookie_related_selector('#gdpr-banner')
        assert is_cookie_related_selector('.gdpr-consent')

    def test_is_cookie_related_selector_third_party(self):
        """Test detection of third-party cookie solutions"""
        assert is_cookie_related_selector('#onetrust-banner-sdk')
        assert is_cookie_related_selector('#CybotCookiebotDialog')

    def test_is_cookie_related_selector_non_cookie(self):
        """Test that non-cookie selectors are not matched"""
        assert not is_cookie_related_selector('#main-navigation')
        assert not is_cookie_related_selector('.sidebar-menu')
        assert not is_cookie_related_selector('[data-testid="submit-button"]')

    def test_is_cookie_related_selector_case_insensitive(self):
        """Test that detection is case-insensitive"""
        assert is_cookie_related_selector('#COOKIE-BANNER')
        assert is_cookie_related_selector('.Cookie-Consent')
        assert is_cookie_related_selector('#ConsentDialog')

    def test_cookie_banner_selectors_no_duplicates(self):
        """Test that there are no duplicate selectors"""
        assert len(COOKIE_BANNER_SELECTORS) == len(set(COOKIE_BANNER_SELECTORS))

    def test_accept_button_selectors_no_duplicates(self):
        """Test that there are no duplicate accept button selectors"""
        assert len(ACCEPT_BUTTON_SELECTORS) == len(set(ACCEPT_BUTTON_SELECTORS))

    def test_cookie_banner_selectors_valid_css(self):
        """Test that all selectors are valid CSS format"""
        for selector in COOKIE_BANNER_SELECTORS:
            # Basic CSS validity checks
            assert isinstance(selector, str)
            assert len(selector) > 0
            # Should start with #, ., or [
            assert selector[0] in ['#', '.', '[']

    def test_accept_button_selectors_valid_format(self):
        """Test that accept button selectors are valid"""
        for selector in ACCEPT_BUTTON_SELECTORS:
            assert isinstance(selector, str)
            assert len(selector) > 0

    def test_priority_ordering_consistent(self):
        """Test that priority ordering is consistent"""
        # Get priorities for first few selectors
        priorities = [get_cookie_banner_priority(s) for s in COOKIE_BANNER_SELECTORS[:5]]

        # Should be in ascending order (0, 1, 2, 3, 4)
        assert priorities == list(range(5))

    def test_cookie_keywords_coverage(self):
        """Test that common cookie keywords are covered"""
        all_selectors = ' '.join(COOKIE_BANNER_SELECTORS).lower()

        keywords = ['cookie', 'consent', 'banner']
        for keyword in keywords:
            assert keyword in all_selectors, f"Missing keyword: {keyword}"

    def test_accept_keywords_coverage(self):
        """Test that common accept button keywords are covered"""
        all_selectors = ' '.join(ACCEPT_BUTTON_SELECTORS).lower()

        keywords = ['accept', 'agree', 'ok']
        for keyword in keywords:
            assert keyword in all_selectors, f"Missing keyword: {keyword}"

    def test_selector_list_ordering_logical(self):
        """Test that selectors are ordered logically"""
        # ID selectors should come before class selectors
        first_class_index = None
        last_id_index = None

        for i, selector in enumerate(COOKIE_BANNER_SELECTORS):
            if selector.startswith('.') and first_class_index is None:
                first_class_index = i
            if selector.startswith('#'):
                last_id_index = i

        if first_class_index and last_id_index:
            # All IDs should come before first class
            assert last_id_index < first_class_index
