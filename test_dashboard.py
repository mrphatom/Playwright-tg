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
