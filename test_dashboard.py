import base64
from types import SimpleNamespace

import pytest
from aiohttp import web

import control_plane as cp
import dashboard


@pytest.fixture
def dashboard_db(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "dashboard-test-secret")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"dashboard-test-session-secret-32bytes"[:32]).decode())
    cp.init_platform_db()
    return path


def test_dashboard_registers_developer_and_integration_routes(dashboard_db):
    paths = {resource.canonical for resource in dashboard.create_dashboard_app().router.resources()}
    assert "/api/v1/check" in paths
    assert "/api/v1/docs" in paths
    assert "/api/v1/keys" in paths
    assert "/api/v1/keys/{key_id}" in paths
    assert "/api/v1/developer/stats" in paths
    assert "/api/admin/analytics" in paths
    assert "/api/admin/banned" in paths
    assert "/api/status" in paths
    assert "/api/status/events" in paths
    assert "/api/admin/runtime" in paths


def test_public_status_payload_is_sanitized_and_timestamped(dashboard_db):
    cp.set_maintenance_state("scheduled", "Planned maintenance", "database update", 9001, incident_id="inc_1")
    payload = dashboard.public_status_payload()
    assert payload["status"] == "scheduled"
    assert payload["message"] == "Planned maintenance"
    assert payload["updated_at"]
    assert payload["incident_id"] == "inc_1"


def test_api_key_boundary_fails_closed_without_bearer_header(dashboard_db):
    request = SimpleNamespace(headers={})
    with pytest.raises(web.HTTPUnauthorized) as error:
        dashboard._require_api_key(request, "check")
    assert "api_key_required" in error.value.text


def test_api_key_boundary_rejects_non_developer_after_role_revocation(dashboard_db):
    cp.ensure_user(42)
    cp.set_user_role(42, cp.ROLE_DEVELOPER)
    created = cp.create_api_key(42, "relay", ["check"])
    cp.set_user_role(42, cp.ROLE_USER)
    request = SimpleNamespace(headers={"Authorization": f"Bearer {created['key']}"})
    with pytest.raises(web.HTTPUnauthorized) as error:
        dashboard._require_api_key(request, "check")
    assert "invalid_api_key" in error.value.text


def test_dashboard_client_has_bounded_bootstrap_and_recovery_states():
    assert "AbortController" in dashboard.HTML
    assert "FETCH_TIMEOUT_MS" in dashboard.HTML
    assert "Promise.allSettled" in dashboard.HTML
    assert "Dashboard data could not be loaded" in dashboard.HTML
    assert "setInterval(()=>refresh().catch(()=>{}),3000)" in dashboard.HTML


def test_public_developer_api_contract_is_machine_readable(dashboard_db):
    response = dashboard.developer_api_docs()
    assert response["base_url"].endswith("playwright-tg-mrphatom.fly.dev")
    assert response["enabled_scopes"] == ["check"]
    assert response["endpoints"][0]["method"] == "POST"
    assert response["endpoints"][0]["path"] == "/api/v1/check"


def test_public_dashboard_session_cipher_fails_closed_without_dedicated_secret(dashboard_db, monkeypatch):
    monkeypatch.delenv("SESSION_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(cp, "public_mode", lambda: True)

    with pytest.raises(RuntimeError, match="SESSION_ENCRYPTION_KEY"):
        cp._dashboard_cipher()


def test_developer_api_check_uses_strict_route_policy(dashboard_db, monkeypatch):
    import bot

    class Body:
        async def read(self, _limit):
            return b'{"url":"https://example.com","extract":"title"}'

    request = SimpleNamespace(
        headers={},
        content_length=64,
        content=Body(),
    )
    monkeypatch.setattr(dashboard, "_require_api_key", lambda _request, _scope: {"user_id": 42, "key_id": "key_test"})
    monkeypatch.setattr(bot, "is_valid_url", lambda _url: True)
    monkeypatch.setattr(bot, "is_domain_allowed", lambda _url: True)
    monkeypatch.setattr(bot, "route_url_allowed", lambda _url, _user_id: False)

    with pytest.raises(web.HTTPBadRequest) as error:
        import asyncio
        asyncio.run(dashboard.api_check_handler(request))
    assert "url_not_allowed" in error.value.text


def test_dashboard_admin_bootstrap_includes_developer_console_access():
    assert "el('developer').hidden=u.role!=='developer' && u.role!=='admin'" in dashboard.HTML


def test_admin_unban_rejects_nonexistent_target_instead_of_reporting_success(dashboard_db, monkeypatch):
    async def body():
        return {"user_id": 424242}

    request = SimpleNamespace(json=body)
    monkeypatch.setattr(dashboard, "_require_admin", lambda _request: (SimpleNamespace(), {"telegram_user_id": 9001}))
    monkeypatch.setattr(dashboard, "_require_csrf", lambda _request, _session: None)

    with pytest.raises(web.HTTPNotFound) as error:
        import asyncio
        asyncio.run(dashboard.admin_unban_handler(request))
    assert "user_not_found" in error.value.text


def test_admin_ban_returns_bad_request_for_non_numeric_user_id(dashboard_db, monkeypatch):
    async def body():
        return {"user_id": "not-a-user"}

    request = SimpleNamespace(json=body)
    monkeypatch.setattr(dashboard, "_require_admin", lambda _request: (SimpleNamespace(), {"telegram_user_id": 9001}))
    monkeypatch.setattr(dashboard, "_require_csrf", lambda _request, _session: None)

    with pytest.raises(web.HTTPBadRequest) as error:
        import asyncio
        asyncio.run(dashboard.admin_ban_handler(request))
    assert "invalid_user_id" in error.value.text


def test_admin_analytics_rejects_malformed_limit_safely(dashboard_db, monkeypatch):
    request = SimpleNamespace(query={"limit": "not-a-number"})
    monkeypatch.setattr(dashboard, "_require_admin", lambda _request: (SimpleNamespace(), {"telegram_user_id": 9001}))

    with pytest.raises(web.HTTPBadRequest) as error:
        import asyncio
        asyncio.run(dashboard.admin_analytics_handler(request))
    assert "invalid_limit" in error.value.text


def test_dashboard_inline_script_receives_a_request_scoped_csp_nonce(monkeypatch):
    request = {}
    monkeypatch.setattr(dashboard, "_session_from_request", lambda _request: {"user_id": 9001})

    import asyncio
    response = asyncio.run(dashboard.index_handler(request))

    assert "__GREYAI_CSP_NONCE__" not in response.text
    assert request["csp_nonce"]
    assert "nonce=\"" in response.text
