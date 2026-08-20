import pytest
import os
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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
    normalize_natural_language_plan,
    mask_sensitive_action,
    normalize_schedule_config,
    calculate_next_schedule_run,
    save_schedule_to_db,
    list_schedules_for_chat,
    deactivate_schedule_in_db,
    restore_schedules_from_db,
    is_web_automation_request,
    build_chat_prompt
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


def test_normalize_plan_preserves_allowlisted_pipeline_actions(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = normalize_natural_language_plan({
        "mode": "check",
        "url": "https://example.com/dashboard",
        "actions": [
            "load_session:x_login",
            "wait:2",
            "extract:.headline",
            "ai_extract:Summarize the page",
            "save_session:x_login",
        ],
    })

    assert plan["actions"] == [
        "load_session:x_login",
        "wait:2",
        "extract:.headline",
        "ai_extract:Summarize the page",
        "save_session:x_login",
    ]


def test_normalize_plan_rejects_unknown_or_unsafe_actions(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    assert normalize_natural_language_plan({
        "mode": "check",
        "url": "https://example.com",
        "actions": ["shell:rm -rf /"],
    }) is None
    assert normalize_natural_language_plan({
        "mode": "check",
        "url": "https://example.com",
        "actions": ["type_password:secret"],
    }) is None


def test_combined_session_login_accepts_screenshot_wording(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = bot.parse_deterministic_login_request(
        "Create a session called 'x_login', then I want you to login https://x.com, "
        "Username = 'mrphatom' Password = 'secret-password'"
    )

    assert plan["mode"] == "login"
    assert "save_session:x_login" in plan["actions"]


def test_combined_session_login_uses_requested_session_name(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = bot.parse_deterministic_login_request(
        "Create a session called x_login, then login to https://x.com with "
        "username 'mrphatom' and password 'secret-password' and remember this login"
    )

    assert plan["mode"] == "login"
    assert "save_session:x_login" in plan["actions"]


def test_natural_language_session_only_commands_are_interpreted():
    import bot

    assert bot.parse_deterministic_management_request("load session 'x_login'") == {
        "mode": "load_session",
        "session_name": "x_login",
    }
    assert bot.parse_deterministic_management_request("use saved session x_login") == {
        "mode": "load_session",
        "session_name": "x_login",
    }
    assert bot.parse_deterministic_management_request("show system health") == {
        "mode": "health"
    }
    assert bot.parse_deterministic_management_request("what can you do") == {
        "mode": "help"
    }


def test_natural_language_management_commands_are_interpreted():
    import bot

    assert bot.parse_deterministic_management_request("show my saved sessions") == {
        "mode": "list_sessions"
    }
    assert bot.parse_deterministic_management_request("list active watchers") == {
        "mode": "list_watchers"
    }
    assert bot.parse_deterministic_management_request("stop watcher abc123") == {
        "mode": "stop_watch",
        "watcher_id": "abc123",
    }
    assert bot.parse_deterministic_management_request("cancel schedule qwe789") == {
        "mode": "unschedule",
        "schedule_id": "qwe789",
    }


def test_natural_language_login_request_builds_masked_browser_actions(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = bot.parse_deterministic_login_request(
        "I want you to login https://x.com, my username is 'mrphatom' "
        "and password is 'secret-password'"
    )

    assert plan["mode"] == "login"
    assert plan["url"] == "https://x.com"
    assert any(action.startswith("type_username:") for action in plan["actions"])
    assert any(action.startswith("click_login_") for action in plan["actions"])
    assert any(action.startswith("wait:") for action in plan["actions"])
    assert all("secret-password" not in bot.mask_sensitive_action(action) for action in plan["actions"])


def test_natural_language_parser_handles_login_without_calling_gemini(monkeypatch):
    import bot

    class FailingModel:
        def generate_content(self, *args, **kwargs):
            raise AssertionError("login credentials must not be sent to Gemini")

    monkeypatch.setattr(bot, "ai_model", FailingModel())
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = asyncio.run(bot.parse_natural_language_intent(
        "Login to https://x.com with username 'mrphatom' and password 'secret-password'"
    ))

    assert plan["mode"] == "login"
    assert plan["url"] == "https://x.com"


def test_natural_language_parser_falls_back_for_unknown_schedule_output(monkeypatch):
    import bot

    class FakeResponse:
        text = '{"mode": "unknown"}'

    class FakeModel:
        def generate_content(self, prompt, generation_config=None):
            return FakeResponse()

    monkeypatch.setattr(bot, "ai_model", FakeModel())
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = asyncio.run(bot.parse_natural_language_intent(
        "Every weekday at 08:00 Europe/London, summarize https://google.com/news "
        "and send me one combined morning briefing"
    ))

    assert plan["mode"] == "schedule"
    assert plan["schedule"]["urls"] == ["https://google.com/news"]


def test_deterministic_web_fallback_uses_selected_session(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = bot.parse_deterministic_web_request(
        "Open https://example.com/dashboard and summarize it",
        default_session_name="x_login",
    )

    assert plan["actions"] == ["load_session:x_login", "ai_extract:it"]


def test_deterministic_web_fallback_handles_check_and_watch(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    check_plan = bot.parse_deterministic_web_request(
        "Please summarize https://example.com/news in three points"
    )
    assert check_plan["mode"] == "check"
    assert check_plan["url"] == "https://example.com/news"
    assert check_plan["actions"] == ["ai_extract:in three points"]

    watch_plan = bot.parse_deterministic_web_request(
        "Monitor https://example.com/store and tell me when Apple Pie is in stock every 2 minutes"
    )
    assert watch_plan["mode"] == "watch"
    assert watch_plan["interval_seconds"] == 120
    assert watch_plan["actions"] == ["condition_ai:Apple Pie is in stock"]


def test_natural_language_parser_preserves_model_action_pipeline(monkeypatch):
    import bot

    class FakeResponse:
        text = json.dumps({
            "mode": "check",
            "url": "https://example.com/dashboard",
            "request": "",
            "condition": "",
            "condition_type": "ai",
            "interval_seconds": 60,
            "actions": ["load_session:x_login", "wait:2", "extract:.headline"],
        })

    class FakeModel:
        def generate_content(self, prompt, generation_config=None):
            return FakeResponse()

    monkeypatch.setattr(bot, "ai_model", FakeModel())
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = asyncio.run(bot.parse_natural_language_intent(
        "Open https://example.com/dashboard using my x_login session, wait two seconds, and extract .headline"
    ))

    assert plan["mode"] == "check"
    assert plan["actions"] == ["load_session:x_login", "wait:2", "extract:.headline"]


def test_natural_language_parser_accepts_fenced_json(monkeypatch):
    import bot

    class FakeResponse:
        text = """```json
{"mode": "watch", "url": "https://example.com", "request": "", "condition": "Apple Pie is in stock", "condition_type": "contains", "interval_seconds": 60}
```"""

    class FakeModel:
        def generate_content(self, prompt, generation_config=None):
            return FakeResponse()

    monkeypatch.setattr(bot, "ai_model", FakeModel())
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = asyncio.run(bot.parse_natural_language_intent("Tell me when Apple Pie is in stock on https://example.com"))

    assert plan["mode"] == "watch"
    assert plan["actions"] == ["condition_contains:Apple Pie is in stock"]


def test_schedule_config_normalizes_timezone_days_urls_and_delivery(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    config = normalize_schedule_config({
        "schedule_time": "08:00",
        "timezone": "Europe/London",
        "days": "weekdays",
        "urls": ["https://example.com/news", "https://example.org/releases"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize the important updates",
    })

    assert config == {
        "schedule_time": "08:00",
        "timezone": "Europe/London",
        "days": [0, 1, 2, 3, 4],
        "urls": ["https://example.com/news", "https://example.org/releases"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize the important updates",
    }


def test_schedule_config_rejects_invalid_timezone_or_url(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    assert normalize_schedule_config({
        "schedule_time": "08:00",
        "timezone": "Not/AZone",
        "days": "daily",
        "urls": ["https://example.com"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize it",
    }) is None
    assert normalize_schedule_config({
        "schedule_time": "08:00",
        "timezone": "UTC",
        "days": "daily",
        "urls": ["javascript:alert(1)"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize it",
    }) is None


def test_schedule_config_normalizes_scheme_less_urls(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    config = normalize_schedule_config({
        "schedule_time": "08:00",
        "timezone": "Europe/London",
        "days": "weekdays",
        "urls": ["google.com/news"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize the latest news",
    })

    assert config["urls"] == ["https://google.com/news"]


def test_deterministic_schedule_fallback_parses_exact_telegram_request(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = bot.parse_deterministic_schedule_request(
        "Every weekday at 08:00 Europe/London, summarize https://google.com/news "
        "and send me one combined morning briefing"
    )

    assert plan["mode"] == "schedule"
    assert plan["schedule"]["schedule_time"] == "08:00"
    assert plan["schedule"]["timezone"] == "Europe/London"
    assert plan["schedule"]["days"] == [0, 1, 2, 3, 4]
    assert plan["schedule"]["urls"] == ["https://google.com/news"]
    assert plan["schedule"]["delivery_mode"] == "combined"


def test_natural_language_schedule_plan_normalizes_to_schedule(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])

    plan = normalize_natural_language_plan({
        "mode": "schedule",
        "schedule_time": "08:00",
        "timezone": "UTC",
        "days": "weekdays",
        "urls": ["https://example.com/news"],
        "delivery_mode": "separate",
        "summary_prompt": "Summarize the latest updates",
    })

    assert plan["mode"] == "schedule"
    assert plan["schedule"]["delivery_mode"] == "separate"
    assert plan["schedule"]["days"] == [0, 1, 2, 3, 4]


def test_schedule_crud_persists_and_deactivates(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", [])
    config = normalize_schedule_config({
        "schedule_time": "08:00",
        "timezone": "UTC",
        "days": "daily",
        "urls": ["https://example.com"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize it",
    })
    next_run = calculate_next_schedule_run(config, datetime(2026, 8, 20, 7, 0, tzinfo=ZoneInfo("UTC")))

    save_schedule_to_db("abc123", 7, 99, config, next_run)
    rows = list_schedules_for_chat(99)

    assert len(rows) == 1
    assert rows[0]["schedule_id"] == "abc123"
    assert rows[0]["config"] == config
    assert deactivate_schedule_in_db("abc123", 99) is True
    assert list_schedules_for_chat(99) == []


def test_restore_schedules_recreates_active_task_and_cancels_cleanly():
    import bot
    config = {
        "schedule_time": "08:00",
        "timezone": "UTC",
        "days": list(range(7)),
        "urls": ["https://example.com"],
        "delivery_mode": "combined",
        "summary_prompt": "Summarize it",
    }
    next_run = datetime.now(ZoneInfo("UTC")) + timedelta(hours=1)
    save_schedule_to_db("restore1", 7, 99, config, next_run)

    async def exercise_restore():
        bot.active_schedules.clear()
        await restore_schedules_from_db(SimpleNamespace())
        assert "restore1" in bot.active_schedules
        task = bot.active_schedules["restore1"]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise_restore())


def test_next_schedule_run_uses_timezone_and_skips_weekends():
    config = {
        "schedule_time": "08:00",
        "timezone": "Europe/London",
        "days": [0, 1, 2, 3, 4],
    }
    now = datetime(2026, 8, 21, 8, 30, tzinfo=ZoneInfo("Europe/London"))

    next_run = calculate_next_schedule_run(config, now)

    assert next_run == datetime(2026, 8, 24, 8, 0, tzinfo=ZoneInfo("Europe/London"))


def test_plain_conversation_is_not_routed_to_web_automation():
    assert is_web_automation_request("What do you think about this idea?") is False
    assert is_web_automation_request("Help me plan a productive morning") is False
    assert is_web_automation_request("Check https://example.com and summarize it") is True
    assert is_web_automation_request("Every weekday at 08:00 summarize https://example.com") is True


def test_login_is_web_automation_request():
    assert is_web_automation_request(
        "Login to https://x.com with username 'mrphatom' and password 'secret-password'"
    ) is True


def test_scheme_less_schedule_is_web_automation_request():
    assert is_web_automation_request(
        "Every weekday at 08:00 Europe/London summarize google.com/news"
    ) is True


def test_chat_prompt_includes_bounded_history_and_current_message():
    history = [
        {"role": "user", "text": f"old-{index}"}
        for index in range(20)
    ]
    prompt = build_chat_prompt("What should I do next?", history)

    assert "What should I do next?" in prompt
    assert "old-19" in prompt
    assert "old-0" not in prompt
    assert len(prompt) < 12000


def test_conversational_reply_uses_gemini_and_remembers_turn(monkeypatch):
    import bot

    class FakeResponse:
        text = "That sounds like a strong idea."

    class FakeModel:
        def generate_content(self, prompt, generation_config=None):
            assert "What do you think?" in prompt
            assert generation_config["temperature"] == 0.7
            return FakeResponse()

    monkeypatch.setattr(bot, "ai_model", FakeModel())
    bot.chat_histories.clear()

    reply = asyncio.run(bot.generate_chat_reply(123, "What do you think?"))
    bot.remember_chat_turn(123, "What do you think?", reply)

    assert reply == "That sounds like a strong idea."
    assert bot.chat_histories[123][-1]["text"] == reply


def test_sensitive_natural_language_actions_are_redacted():
    assert mask_sensitive_action("ai_extract:read my private account") == "ai_extract:***REDACTED***"
    assert mask_sensitive_action("condition_ai:alert me about my order") == "condition_ai:***REDACTED***"
    assert mask_sensitive_action("condition_contains:secret phrase") == "condition_contains:***REDACTED***"


def test_browser_task_retry_recovers_transient_failure(monkeypatch):
    import bot
    attempts = []

    async def flaky_task(url, actions, user_id, status_msg=None):
        attempts.append(url)
        if len(attempts) == 1:
            raise RuntimeError("temporary browser failure")
        return {"title": "Recovered", "extracted": [], "screenshot": "unused.png"}

    monkeypatch.setattr(bot, "run_browser_task", flaky_task)
    result = asyncio.run(bot.run_browser_task_with_retry(
        "https://example.com", [], 7, "operation123", attempts=2
    ))

    assert result["title"] == "Recovered"
    assert attempts == ["https://example.com", "https://example.com"]


def test_restricted_handler_fails_closed_without_allowlist(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "ALLOWED_USERS", set())
    called = False

    @bot.restricted
    async def protected(update, context):
        nonlocal called
        called = True

    update = SimpleNamespace(effective_user=SimpleNamespace(id=123), message=None)
    asyncio.run(protected(update, None))

    assert called is False


def test_domain_whitelist_filtering(monkeypatch):
    """Verify domain whitelist correctly permits or blocks URLs."""
    import bot
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", ["github.com", "amazon.com"])
    
    assert is_domain_allowed("https://github.com/login") is True
    assert is_domain_allowed("https://sub.github.com/page") is True
    assert is_domain_allowed("https://amazon.com/dp/123") is True
    assert is_domain_allowed("https://malicious-site.com") is False

