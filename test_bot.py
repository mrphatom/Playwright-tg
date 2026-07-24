import pytest
from bot import is_valid_url, sanitize_session_name, truncate_text

def test_url_validation_strictness():
    """Ensures URL validator utility correctly handles scheme boundaries."""
    assert is_valid_url("https://example.com") is True
    assert is_valid_url("http://example.com/path?args=1") is True
    # Should reject malformed or non-http protocols for safety
    assert is_valid_url("ftp://server.com") is False
    assert is_valid_url("invalid-url-string") is False

def test_path_traversal_prevention():
    """Ensures malicious session strings cannot write outside the sessions directory."""
    # Normal input
    assert sanitize_session_name("my_twitter_login") == "my_twitter_login"
    
    # Malicious inputs
    # ../../ = 6 invalid characters, so we expect 6 underscores
    assert sanitize_session_name("../../etc/passwd") == "______etc_passwd"
    assert sanitize_session_name("C:\\Windows\\System32") == "C__Windows_System32"
    assert sanitize_session_name("login(1)!") == "login_1__"

def test_telegram_truncation():
    """Ensures strings are safely chopped to respect Telegram API boundaries."""
    short_text = "Hello World"
    assert truncate_text(short_text, 100) == short_text
    
    long_text = "A" * 5000
    truncated = truncate_text(long_text, 4000)
    assert len(truncated) <= 4000
    assert truncated.endswith("...[Truncated]")
