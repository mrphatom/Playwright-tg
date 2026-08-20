import pytest
from aiohttp import web
from types import SimpleNamespace

import control_plane as cp
import dashboard


@pytest.fixture
def dashboard_db(tmp_path, monkeypatch):
    path = tmp_path / "dashboard.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "dashboard-test-secret")
    cp.init_platform_db()
    return path


def test_dashboard_registers_developer_and_integration_routes(dashboard_db):
    paths = {resource.canonical for resource in dashboard.create_dashboard_app().router.resources()}
    assert "/api/v1/check" in paths
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
