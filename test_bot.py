import pytest
import os
import sqlite3
import json

# Set environment variable BEFORE importing bot module so bot uses test_telescout.db
os.environ["DB_PATH"] = "test_telescout.db"

from bot import (
    is_valid_url, 
    sanitize_session_name, 
    truncate_text, 
    is_domain_allowed,
    save_encrypted_session,
    load_encrypted_session,
    init_db,
    normalize_natural_language_plan
)

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield
    if os.path.exists("test_telescout.db"):
        os.remove("test_telescout.db")

def test_url_validation_strictness():
    assert is_valid_url("https://example.com") is True
    assert is_valid_url("http://example.com/path?args=1") is True
    assert is_valid_url("ftp://server.com") is False

def test_path_traversal_prevention():
    assert sanitize_session_name("my_twitter_login") == "my_twitter_login"
    assert sanitize_session_name("../../etc/passwd") == "______etc_passwd"

def test_telegram_truncation():
    long_text = "A" * 5000
    truncated = truncate_text(long_text, 4000)
    assert len(truncated) <= 4000
    assert truncated.endswith("...[Truncated]")

def test_encrypted_session_storage():
    """Verify session JSON is encrypted at rest in SQLite and decrypted correctly."""
    user_id = 12345
    session_name = "test_session"
    dummy_cookies = {"cookies": [{"name": "auth_token", "value": "secret_123"}]}
    
    # Save
    save_encrypted_session(user_id, session_name, dummy_cookies)
    
    # Direct DB Inspection (verify data is NOT raw JSON)
    with sqlite3.connect("test_telescout.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_data FROM sessions WHERE user_id = ? AND name = ?", (user_id, session_name))
        raw_db_val = cursor.fetchone()[0]
        assert "secret_123" not in raw_db_val  # Must be encrypted!

    # Load & Decrypt
    decrypted = load_encrypted_session(user_id, session_name)
    assert decrypted == dummy_cookies

def test_natural_language_check_plan_normalizes_valid_input(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = normalize_natural_language_plan({
        "mode": "check",
        "url": "https://example.com/products",
        "request": "Summarize the product title",
        "condition": "",
        "condition_type": "ai",
        "interval_seconds": 60,
    })

    assert plan == {
        "mode": "check",
        "url": "https://example.com/products",
        "actions": ["ai_extract:Summarize the product title"],
        "condition": "",
        "condition_type": "ai",
        "interval_seconds": 60,
    }


def test_natural_language_watch_plan_clamps_interval_and_uses_condition(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = normalize_natural_language_plan({
        "mode": "watch",
        "url": "https://example.com/products",
        "request": "",
        "condition": "Apple Pie is in stock",
        "condition_type": "contains",
        "interval_seconds": 5,
    })

    assert plan["mode"] == "watch"
    assert plan["actions"] == ["condition_contains:Apple Pie is in stock"]
    assert plan["interval_seconds"] == 30


def test_natural_language_plan_rejects_invalid_or_disallowed_urls(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", ["allowed.example"])

    assert normalize_natural_language_plan({
        "mode": "check",
        "url": "javascript:alert(1)",
        "request": "read it",
    }) is None
    assert normalize_natural_language_plan({
        "mode": "check",
        "url": "https://blocked.example/page",
        "request": "read it",
    }) is None


def test_domain_whitelist_filtering(monkeypatch):
    """Verify domain whitelist correctly permits or blocks URLs."""
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", ["github.com", "amazon.com"])
    
    assert is_domain_allowed("https://github.com/login") is True
    assert is_domain_allowed("https://sub.github.com/page") is True
    assert is_domain_allowed("https://amazon.com/dp/123") is True
    assert is_domain_allowed("https://malicious-site.com") is False

