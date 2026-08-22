"""Authenticated operations dashboard for GreyAI.

The dashboard is intentionally small and server-authoritative: it exposes only
redacted metadata and checks role/resource permissions on every request.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import sys
from typing import Any

from aiohttp import web

from api_contract import developer_api_contract
from control_plane import (
    authenticate_api_key,
    check_api_key_rate_limit,
    consume_quota,
    create_api_key,
    enqueue_user_notification,
    ensure_user,
    exchange_dashboard_login_token,
    get_admin_analytics,
    get_appeal,
    get_dashboard_session,
    get_developer_stats,
    get_latest_runtime_snapshot,
    get_maintenance_state,
    get_queue_stats,
    get_referral_stats,
    get_user,
    is_admin,
    is_developer,
    list_api_keys,
    list_appeals,
    list_maintenance_events,
    list_operations,
    list_referrals,
    list_reports,
    list_session_metadata,
    list_users_by_status,
    record_admin_action,
    record_developer_audit,
    resolve_appeal,
    resolve_report,
    revoke_api_key,
    revoke_dashboard_session,
    search_users,
    set_user_status,
)

SESSION_COOKIE = "greyai_session"
CSRF_COOKIE = "greyai_csrf"


def _json_rows(rows):
    return [dict(row) for row in rows]


def developer_api_docs() -> dict[str, Any]:
    """Return the redacted, authoritative contract used by Grey’s API guidance."""
    return developer_api_contract(os.getenv("DASHBOARD_BASE_URL"))


async def developer_api_docs_handler(request: web.Request):
    return web.json_response(developer_api_docs())


def _session_from_request(request: web.Request):
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    session = get_dashboard_session(raw)
    if not session:
        return None
    user = get_user(session["user_id"])
    if not user or user["status"] == "banned":
        return None
    return session, user


def _require_session(request: web.Request):
    current = _session_from_request(request)
    if not current:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "authentication_required"}), content_type="application/json")
    return current


def _require_admin(request: web.Request):
    session, user = _require_session(request)
    if not is_admin(user["telegram_user_id"]):
        raise web.HTTPForbidden(text=json.dumps({"error": "administrator_required"}), content_type="application/json")
    return session, user


def _require_api_key(request: web.Request, required_scope: str | None = None):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "api_key_required"}), content_type="application/json")
    principal = authenticate_api_key(authorization[7:].strip())
    if not principal:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "invalid_api_key"}), content_type="application/json")
    if required_scope and required_scope not in principal["scopes"]:
        record_developer_audit(None, principal["user_id"], principal["key_id"], "api_scope_check", "denied", {"scope": required_scope})
        raise web.HTTPForbidden(text=json.dumps({"error": "scope_required", "scope": required_scope}), content_type="application/json")
    allowed, used, limit = check_api_key_rate_limit(principal["key_id"], principal["user_id"], principal["rate_limit_per_minute"])
    if not allowed:
        raise web.HTTPTooManyRequests(text=json.dumps({"error": "api_rate_limit_exceeded", "used": used, "limit": limit}), content_type="application/json", headers={"Retry-After": "60"})
    return principal


def _require_developer(request: web.Request):
    session, user = _require_session(request)
    if not is_developer(user["telegram_user_id"]):
        raise web.HTTPForbidden(text=json.dumps({"error": "developer_capability_required"}), content_type="application/json")
    return session, user


def _require_csrf(request: web.Request, session) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not supplied or not cookie or not secrets.compare_digest(supplied, cookie) or not secrets.compare_digest(supplied, session["csrf_token"]):
        raise web.HTTPForbidden(text=json.dumps({"error": "csrf_failed"}), content_type="application/json")


def _bounded_query_limit(request: web.Request, default: int = 25, maximum: int = 100) -> int:
    raw = request.query.get("limit", str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_limit"}), content_type="application/json")
    if value < 1:
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_limit"}), content_type="application/json")
    return min(value, maximum)


async def _json_object(request: web.Request) -> dict[str, Any]:
    """Decode a mutation body without exposing parser errors or accepting arrays/scalars."""
    try:
        data = await request.json()
    except (ValueError, TypeError, UnicodeDecodeError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text=json.dumps({"error": "json_object_required"}), content_type="application/json")
    return data


@web.middleware
async def security_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    nonce = request.get("csp_nonce")
    script_source = "'self'" + (f" 'nonce-{nonce}'" if nonce else "")
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src {script_source}; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store"
    return response


async def login_handler(request: web.Request):
    token = request.query.get("token", "")
    session = exchange_dashboard_login_token(token)
    if not session:
        raise web.HTTPUnauthorized(text="This dashboard link is invalid or expired.")
    response = web.HTTPFound("/")
    response.set_cookie(SESSION_COOKIE, session["session"], httponly=True, secure=True, samesite="Lax", max_age=86400)
    response.set_cookie(CSRF_COOKIE, session["csrf"], httponly=False, secure=True, samesite="Lax", max_age=86400)
    return response


async def logout_handler(request: web.Request):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        revoke_dashboard_session(raw)
    response = web.HTTPFound("/")
    response.del_cookie(SESSION_COOKIE)
    response.del_cookie(CSRF_COOKIE)
    return response


async def me_handler(request: web.Request):
    _, user = _require_session(request)
    user_data = dict(user)
    user_data.pop("status_reason", None)
    return web.json_response(user_data)


async def operations_handler(request: web.Request):
    _, user = _require_session(request)
    user_id = None if is_admin(user["telegram_user_id"]) and request.query.get("scope") == "all" else user["telegram_user_id"]
    return web.json_response({"operations": _json_rows(list_operations(user_id, 100)), "sessions": _json_rows(list_session_metadata(user_id, 100))})


def public_status_payload() -> dict[str, Any]:
    state = get_maintenance_state()
    return {"status": state.get("mode", "operational"), "message": state.get("message", ""), "reason": state.get("reason", ""), "incident_id": state.get("incident_id"), "started_at": state.get("started_at"), "ends_at": state.get("ends_at"), "updated_at": state.get("updated_at")}


async def public_status_handler(request: web.Request):
    return web.json_response(public_status_payload())


MANUAL_CHALLENGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GreyAI manual challenge</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#10141c;color:#f4f7fb}main{background:#192231;border:1px solid #334155;border-radius:16px;padding:1.25rem}img{display:block;width:100%;max-height:70vh;object-fit:contain;background:#fff;border-radius:10px;cursor:crosshair}button,input{font:inherit;padding:.7rem 1rem;border-radius:9px;border:1px solid #64748b;margin:.25rem}button{cursor:pointer;background:#93c5fd;color:#0f172a;font-weight:700}input{background:#0f172a;color:#f4f7fb}.muted{color:#cbd5e1}.status{min-height:1.5rem}</style>
</head>
<body><main>
<h1>GreyAI manual challenge handoff</h1>
<p class="muted">Complete the site’s CAPTCHA, MFA, or security check yourself. GreyAI will not solve or bypass it. This private link expires automatically.</p>
<p id="status" class="status">Connecting…</p>
<img id="screen" alt="Current browser challenge view">
<div><button id="scroll-up" type="button">Scroll up</button><button id="scroll-down" type="button">Scroll down</button><button id="done" type="button">I’m done — resume GreyAI</button><button id="cancel" type="button">Cancel task</button></div>
<div><input id="text" maxlength="128" autocomplete="one-time-code" placeholder="Optional one-time code"><button id="type" type="button">Type code</button></div>
<p class="muted">Click the screenshot to click the corresponding location in the live page. Allowed keyboard controls: Enter, Tab, Escape, arrows, and Backspace.</p>
<script nonce="__GREYAI_CSP_NONCE__">
const token=__GREYAI_TOKEN__; const statusEl=document.getElementById('status'); const screen=document.getElementById('screen');
const endpoint=(suffix)=>`/challenge/${token}/${suffix}`;
async function send(suffix,body={}){const r=await fetch(endpoint(suffix),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});const data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.error||'handoff request failed');return data}
async function poll(){try{const r=await fetch(endpoint('status'),{cache:'no-store'});const data=await r.json();if(!r.ok)throw new Error(data.error||'handoff expired');statusEl.textContent=`${data.challenge_kind} challenge — ${data.remaining_seconds}s remaining — ${data.status}`;if(data.status==='waiting'){screen.src=endpoint('screenshot')+'?t='+Date.now();setTimeout(poll,2000)}else{screen.remove();}}catch(e){statusEl.textContent=e.message;}}
screen.addEventListener('click',async e=>{const r=screen.getBoundingClientRect();try{await send('action',{type:'click',x:(e.clientX-r.left)*screen.naturalWidth/r.width,y:(e.clientY-r.top)*screen.naturalHeight/r.height});statusEl.textContent='Click sent.';screen.src=endpoint('screenshot')+'?t='+Date.now()}catch(err){statusEl.textContent=err.message}});
document.getElementById('scroll-up').onclick=()=>send('action',{type:'scroll',delta:-700}).catch(e=>statusEl.textContent=e.message);
document.getElementById('scroll-down').onclick=()=>send('action',{type:'scroll',delta:700}).catch(e=>statusEl.textContent=e.message);
document.getElementById('done').onclick=async()=>{try{await send('complete');statusEl.textContent='Resume requested. You can close this page.'}catch(e){statusEl.textContent=e.message}};
document.getElementById('cancel').onclick=async()=>{try{await send('cancel');statusEl.textContent='Task cancelled.'}catch(e){statusEl.textContent=e.message}};
document.getElementById('type').onclick=async()=>{const input=document.getElementById('text');try{await send('action',{type:'type',text:input.value});input.value='';statusEl.textContent='Code typed into the live page.'}catch(e){statusEl.textContent=e.message}};
document.addEventListener('keydown',e=>{if(['Enter','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Backspace'].includes(e.key)){e.preventDefault();send('action',{type:'key',key:e.key}).catch(err=>statusEl.textContent=err.message)}});poll();
</script></main></body></html>"""


def _bot_runtime_module():
    """Return the live bot module, including when it was launched as ``__main__``.

    ``python bot.py`` executes the file under ``__main__``. Importing ``bot`` from
    a request handler would execute a second module instance with a separate
    in-memory handoff registry, making fresh handoff URLs look expired.
    """
    running_main = sys.modules.get("__main__")
    if running_main is not None and hasattr(running_main, "manual_challenge_status"):
        return running_main
    bot_module = sys.modules.get("bot")
    if bot_module is not None:
        return bot_module
    import bot
    return bot


def _challenge_token(request: web.Request) -> str:
    token = str(request.match_info.get("token", ""))
    if not token or len(token) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise web.HTTPNotFound(text="handoff_not_found")
    return token


async def challenge_page_handler(request: web.Request):
    token = _challenge_token(request)
    bot_runtime = _bot_runtime_module()
    if not bot_runtime.manual_challenge_status(token):
        raise web.HTTPNotFound(text="handoff_not_found_or_expired")
    nonce = secrets.token_urlsafe(18)
    html = MANUAL_CHALLENGE_HTML.replace("__GREYAI_CSP_NONCE__", nonce).replace("__GREYAI_TOKEN__", json.dumps(token))
    request["csp_nonce"] = nonce
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


async def challenge_status_handler(request: web.Request):
    token = _challenge_token(request)
    bot_runtime = _bot_runtime_module()
    status = bot_runtime.manual_challenge_status(token)
    if not status:
        raise web.HTTPNotFound(text=json.dumps({"error": "handoff_not_found_or_expired"}), content_type="application/json")
    return web.json_response(status, headers={"Cache-Control": "no-store"})


async def challenge_screenshot_handler(request: web.Request):
    token = _challenge_token(request)
    bot_runtime = _bot_runtime_module()
    image = await bot_runtime.manual_challenge_screenshot(token)
    if image is None:
        raise web.HTTPNotFound(text="handoff_not_found_or_expired")
    return web.Response(body=image, content_type="image/png", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


async def _challenge_action_handler(request: web.Request, action_name: str):
    token = _challenge_token(request)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
    if not isinstance(body, dict) or len(json.dumps(body)) > 2048:
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_action"}), content_type="application/json")
    bot_runtime = _bot_runtime_module()
    if action_name == "action":
        ok, result = await bot_runtime.manual_challenge_action(token, body)
    elif action_name == "complete":
        ok, result = await bot_runtime.complete_manual_challenge(token)
    else:
        ok, result = await bot_runtime.cancel_manual_challenge(token)
    if not ok:
        exception_type = web.HTTPGone if "expired" in result or "not_found" in result else web.HTTPConflict
        raise exception_type(text=json.dumps({"error": result}), content_type="application/json")
    return web.json_response({"ok": True, "status": result}, headers={"Cache-Control": "no-store"})


async def challenge_action_handler(request: web.Request):
    return await _challenge_action_handler(request, "action")


async def challenge_complete_handler(request: web.Request):
    return await _challenge_action_handler(request, "complete")


async def challenge_cancel_handler(request: web.Request):
    return await _challenge_action_handler(request, "cancel")


async def public_maintenance_events_handler(request: web.Request):
    events = []
    for row in list_maintenance_events(50):
        events.append({"event_id": row["event_id"], "mode": row["mode"], "message": row["message"], "reason": row["reason"], "incident_id": row["incident_id"], "created_at": row["created_at"]})
    return web.json_response({"events": events})


async def admin_runtime_handler(request: web.Request):
    _require_admin(request)
    snapshot = get_latest_runtime_snapshot("crash")
    return web.json_response({"queue": get_queue_stats(), "maintenance": public_status_payload(), "latest_crash_snapshot": ({"snapshot_id": snapshot["snapshot_id"], "incident_id": snapshot["incident_id"], "snapshot_kind": snapshot["snapshot_kind"], "created_at": snapshot["created_at"]} if snapshot else None)})


async def health_handler(request: web.Request):
    _, user = _require_session(request)
    operations = list_operations(None if is_admin(user["telegram_user_id"]) and request.query.get("scope") == "all" else user["telegram_user_id"], 100)
    response = {"status": "ok", "role": user["role"], "operations": len(operations), "process": {"pid": os.getpid()}, "maintenance": public_status_payload()}
    if not is_admin(user["telegram_user_id"]):
        response["maintenance"].pop("reason", None)
        response["queue"] = {"queued": None, "running": None}
    else:
        response["queue"] = get_queue_stats()
    return web.json_response(response)


async def api_check_handler(request: web.Request):
    principal = _require_api_key(request, "check")
    max_body_size = 16 * 1024
    if request.content_length and request.content_length > max_body_size:
        raise web.HTTPRequestEntityTooLarge(max_size=max_body_size, actual_size=request.content_length)
    body = await request.content.read(max_body_size + 1)
    if len(body) > max_body_size:
        raise web.HTTPRequestEntityTooLarge(max_size=max_body_size, actual_size=len(body))
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text=json.dumps({"error": "json_object_required"}), content_type="application/json")
    url = str(data.get("url", "")).strip()[:2048]
    extract = str(data.get("extract", "Summarize the important facts on this page.")).strip()[:500]
    if not url:
        raise web.HTTPBadRequest(text=json.dumps({"error": "url_required"}), content_type="application/json")

    # Resolve the live runtime module so script execution cannot create a second
    # bot instance with separate queue, provider, or handoff state.
    bot_runtime = _bot_runtime_module()

    if not bot_runtime.is_valid_url(url) or not bot_runtime.route_url_allowed(url, principal["user_id"]):
        record_developer_audit(None, principal["user_id"], principal["key_id"], "api_check", "denied", {"reason": "url_not_allowed"})
        raise web.HTTPBadRequest(text=json.dumps({"error": "url_not_allowed"}), content_type="application/json")
    allowed_quota, used, limit = consume_quota(principal["user_id"])
    if not allowed_quota:
        record_developer_audit(None, principal["user_id"], principal["key_id"], "api_check", "denied", {"reason": "quota_exceeded"})
        raise web.HTTPTooManyRequests(text=json.dumps({"error": "quota_exceeded", "used": used, "limit": limit}), content_type="application/json")

    operation_id = "api_" + secrets.token_hex(6)
    bot_runtime.create_operation(operation_id, principal["user_id"], None, "api_check", url, {"api_key_id": principal["key_id"], "source": "telegram_integration"})
    screenshot_path = None
    try:
        result = await bot_runtime.run_browser_request(
            operation_id, principal["user_id"], None, "api_check",
            lambda: asyncio.wait_for(bot_runtime.run_browser_task_with_retry(url, [f"ai_extract:{extract}"], principal["user_id"], operation_id), timeout=bot_runtime.COMMAND_TIMEOUT + 5),
        )
        screenshot_path = result.get("screenshot")
        return web.json_response({"ok": True, "operation_id": operation_id, "title": str(result.get("title", ""))[:300], "url": url, "extracted": [str(item)[:4000] for item in result.get("extracted", [])[:10]]})
    except bot_runtime.QueueUnavailable:
        bot_runtime.update_operation(operation_id, "rejected")
        raise web.HTTPServiceUnavailable(text=json.dumps({"error": "maintenance", "operation_id": operation_id}), content_type="application/json")
    except bot_runtime.QueueRejected:
        bot_runtime.update_operation(operation_id, "rejected")
        raise web.HTTPTooManyRequests(text=json.dumps({"error": "queue_full", "operation_id": operation_id}), content_type="application/json")
    except asyncio.TimeoutError:
        bot_runtime.update_operation(operation_id, "failed")
        raise web.HTTPGatewayTimeout(text=json.dumps({"error": "browser_timeout", "operation_id": operation_id}), content_type="application/json")
    except Exception:
        bot_runtime.update_operation(operation_id, "failed")
        raise web.HTTPBadGateway(text=json.dumps({"error": "browser_check_failed", "operation_id": operation_id}), content_type="application/json")
    finally:
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except OSError:
                pass


async def developer_keys_handler(request: web.Request):
    _, user = _require_developer(request)
    return web.json_response({"keys": list_api_keys(user["telegram_user_id"])})


async def developer_key_create_handler(request: web.Request):
    session, user = _require_developer(request)
    _require_csrf(request, session)
    data = await _json_object(request)
    scopes = data.get("scopes", ["check"])
    if isinstance(scopes, str):
        scopes = scopes.split(",")
    if not isinstance(scopes, list):
        raise web.HTTPBadRequest(text=json.dumps({"error": "scopes_must_be_a_list"}), content_type="application/json")
    try:
        created = create_api_key(user["telegram_user_id"], str(data.get("name", "")), scopes, int(data.get("rate_limit_per_minute", 30)))
    except (PermissionError, ValueError, TypeError) as exc:
        raise web.HTTPBadRequest(text=json.dumps({"error": str(exc)}), content_type="application/json")
    return web.json_response(created, status=201)


async def developer_key_revoke_handler(request: web.Request):
    session, user = _require_developer(request)
    _require_csrf(request, session)
    key_id = request.match_info["key_id"]
    if not revoke_api_key(key_id, user["telegram_user_id"]):
        raise web.HTTPNotFound(text=json.dumps({"error": "api_key_not_found"}), content_type="application/json")
    return web.json_response({"ok": True, "key_id": key_id})


async def developer_stats_handler(request: web.Request):
    _, user = _require_developer(request)
    return web.json_response(get_developer_stats(user["telegram_user_id"]))


async def referrals_handler(request: web.Request):
    _, user = _require_session(request)
    return web.json_response(get_referral_stats(user["telegram_user_id"]))


async def admin_referrals_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"referrals": _json_rows(list_referrals(request.query.get("status"), 100))})


async def admin_users_handler(request: web.Request):
    _require_admin(request)
    query = request.query.get("q", "")
    return web.json_response({"users": _json_rows(search_users(query, 100))})


async def admin_analytics_handler(request: web.Request):
    _require_admin(request)
    return web.json_response(get_admin_analytics(_bounded_query_limit(request, 25, 100)))


async def admin_banned_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"users": _json_rows(list_users_by_status("banned", _bounded_query_limit(request, 100, 200)))})


async def admin_reports_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"reports": _json_rows(list_reports(request.query.get("status", "open"), 100))})


async def admin_appeals_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"appeals": _json_rows(list_appeals(request.query.get("status", "open"), 100))})


async def admin_ban_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    data = await _json_object(request)
    try:
        target_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_user_id"}), content_type="application/json")
    if target_id <= 0:
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_user_id"}), content_type="application/json")
    target = get_user(target_id)
    if target and target["role"] == "admin":
        raise web.HTTPForbidden(text=json.dumps({"error": "admin_target_forbidden"}), content_type="application/json")
    ensure_user(target_id)
    reason = str(data.get("reason", "administrator action"))[:500]
    set_user_status(target_id, "banned", reason)
    action_id = record_admin_action(admin["telegram_user_id"], "ban_user", target_id, reason)
    enqueue_user_notification(target_id, "moderation", "GreyAI account access update", f"Your GreyAI account has been banned. Reason: {reason}\n\nIf you believe this is incorrect, submit an appeal with /appeal.", f"dashboard:moderation:ban:{action_id}")
    return web.json_response({"ok": True, "action_id": action_id, "notification_queued": True})


async def admin_unban_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    data = await _json_object(request)
    try:
        target_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_user_id"}), content_type="application/json")
    if target_id <= 0:
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_user_id"}), content_type="application/json")
    if not get_user(target_id):
        raise web.HTTPNotFound(text=json.dumps({"error": "user_not_found"}), content_type="application/json")
    set_user_status(target_id, "active", "administrator unbanned user")
    action_id = record_admin_action(admin["telegram_user_id"], "unban_user", target_id, "administrator unbanned user")
    enqueue_user_notification(target_id, "moderation", "GreyAI account access restored", "An administrator restored access to your GreyAI account. You may use the bot again.", f"dashboard:moderation:unban:{action_id}")
    return web.json_response({"ok": True, "action_id": action_id, "notification_queued": True})


async def admin_review_report_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    report_id = request.match_info["report_id"]
    data = await _json_object(request)
    status = str(data.get("status", "reviewing"))
    resolution = str(data.get("resolution", "reviewed by administrator"))[:4000]
    if not resolve_report(report_id, admin["telegram_user_id"], status, resolution):
        raise web.HTTPNotFound(text=json.dumps({"error": "report_not_found"}), content_type="application/json")
    action_id = record_admin_action(admin["telegram_user_id"], "review_report", None, resolution, {"report_id": report_id, "status": status})
    return web.json_response({"ok": True, "action_id": action_id})


async def admin_resolve_appeal_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    appeal_id = request.match_info["appeal_id"]
    data = await _json_object(request)
    status = str(data.get("status", "reviewing"))
    resolution = str(data.get("resolution", "reviewed by administrator"))[:4000]
    appeal = get_appeal(appeal_id)
    if not appeal or not resolve_appeal(appeal_id, admin["telegram_user_id"], status, resolution):
        raise web.HTTPNotFound(text=json.dumps({"error": "appeal_not_found"}), content_type="application/json")
    action_id = record_admin_action(admin["telegram_user_id"], "resolve_appeal", appeal["user_id"], resolution, {"appeal_id": appeal_id, "status": status})
    outcome = "accepted" if status == "resolved" else "denied" if status == "denied" else status
    enqueue_user_notification(appeal["user_id"], "moderation", "GreyAI appeal decision", f"Your appeal {appeal_id} was updated to {outcome}. Administrator resolution: {resolution}", f"dashboard:moderation:appeal:{action_id}")
    return web.json_response({"ok": True, "action_id": action_id, "notification_queued": True})


async def websocket_handler(request: web.Request):
    _require_session(request)
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    try:
        while True:
            current = _session_from_request(request)
            if not current:
                break
            _, user = current
            scope = None if is_admin(user["telegram_user_id"]) and request.query.get("scope") == "all" else user["telegram_user_id"]
            await ws.send_json({"type": "snapshot", "health": {"status": "ok", "pid": os.getpid()}, "operations": _json_rows(list_operations(scope, 50))})
            await asyncio.sleep(3)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        await ws.close()
    return ws


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>GreyAI Control Room</title>
<style>
:root{--bg:#080d19;--surface:#101827;--surface-2:#151f31;--surface-3:#1b2940;--border:#263650;--text:#f1f5ff;--muted:#9aa9c4;--subtle:#6f7e9b;--accent:#7ca4ff;--accent-strong:#4d7df3;--success:#57d6a0;--warning:#f0c674;--danger:#ff7d8b;--shadow:0 18px 48px rgba(0,0,0,.18);--radius:14px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 10% 0%,#162442 0,#0b1220 28rem,var(--bg) 65%);color:var(--text);line-height:1.5}body,button,input{font:inherit}button,input{font-size:.95rem}button{border:1px solid transparent;border-radius:10px;min-height:42px;padding:.65rem .9rem;cursor:pointer;transition:background .18s ease,border-color .18s ease,transform .18s ease}button:hover{transform:translateY(-1px)}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid rgba(124,164,255,.52);outline-offset:3px}button:disabled{cursor:not-allowed;opacity:.55;transform:none}.button-primary{background:var(--accent-strong);color:white}.button-primary:hover{background:#5d89f5}.button-secondary{background:transparent;border-color:var(--border);color:var(--text)}.button-secondary:hover{background:var(--surface-3);border-color:#3a5279}.button-danger{background:rgba(255,125,139,.12);border-color:rgba(255,125,139,.35);color:#ffabb4}.button-success{background:rgba(87,214,160,.12);border-color:rgba(87,214,160,.35);color:#8ce8bd}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.skip-link{position:fixed;top:12px;left:12px;z-index:20;transform:translateY(-160%);background:var(--surface-3);color:var(--text);padding:.7rem 1rem;border-radius:8px}.skip-link:focus{transform:none}.app-shell{min-height:100vh}.topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:1rem;min-height:76px;padding:0 clamp(1rem,3vw,2.75rem);background:rgba(8,13,25,.86);border-bottom:1px solid rgba(38,54,80,.8);backdrop-filter:blur(16px)}.brand{display:flex;align-items:center;gap:.8rem;min-width:230px}.brand-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:linear-gradient(145deg,#90b5ff,#527bf1);color:#081225;font-weight:900;letter-spacing:-.08em}.brand-title{font-weight:800;letter-spacing:-.03em}.brand-subtitle{display:block;color:var(--muted);font-size:.76rem;font-weight:500;letter-spacing:.02em}.topbar-spacer{flex:1}.status-chip{display:inline-flex;align-items:center;gap:.5rem;border:1px solid rgba(87,214,160,.3);background:rgba(87,214,160,.1);color:#9aefc8;padding:.45rem .7rem;border-radius:999px;font-size:.82rem;font-weight:700}.status-dot{width:8px;height:8px;border-radius:50%;background:currentColor;box-shadow:0 0 0 4px rgba(87,214,160,.1)}.user-chip{color:var(--muted);font-size:.86rem}.nav-toggle{display:none;background:transparent;border-color:var(--border);color:var(--text);padding:.5rem .65rem}.layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:clamp(1rem,3vw,2.5rem);max-width:1480px;margin:0 auto;padding:2rem clamp(1rem,3vw,2.75rem)}.sidebar{position:sticky;top:100px;align-self:start}.nav-label{color:var(--subtle);font-size:.72rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin:0 0 .75rem .7rem}.nav-list{display:grid;gap:.35rem}.nav-button{display:flex;align-items:center;width:100%;background:transparent;color:var(--muted);text-align:left;border-color:transparent;padding:.7rem .75rem}.nav-button:hover,.nav-button[aria-current="true"]{background:var(--surface-2);border-color:var(--border);color:var(--text)}.nav-icon{width:1.5rem;color:var(--accent);font-weight:800}.sidebar-footer{margin-top:2rem;padding:.9rem;border-top:1px solid var(--border);color:var(--muted);font-size:.86rem}.content{min-width:0}.page-section{scroll-margin-top:100px;margin-bottom:2rem}.page-header{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin-bottom:1.25rem}.eyebrow{margin:0 0 .35rem;color:var(--accent);font-size:.75rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase}.page-header h1,.page-header h2{margin:0;letter-spacing:-.04em;line-height:1.12}.page-header h1{font-size:clamp(2rem,4vw,3.35rem)}.page-header h2{font-size:1.55rem}.page-header p{max-width:680px;margin:.65rem 0 0;color:var(--muted)}.last-updated{color:var(--subtle);font-size:.8rem;white-space:nowrap}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.85rem;margin-bottom:1rem}.metric-card{padding:1rem 1.05rem;background:linear-gradient(140deg,rgba(21,31,49,.98),rgba(15,24,39,.98));border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}.metric-label{display:block;color:var(--muted);font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em}.metric-value{display:block;margin-top:.25rem;font-size:1.55rem;font-weight:800;letter-spacing:-.04em}.metric-detail{display:block;margin-top:.25rem;color:var(--subtle);font-size:.78rem}.section-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.75fr);gap:1rem}.panel{min-width:0;background:rgba(16,24,39,.9);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:1.15rem}.panel + .panel{margin-top:1rem}.panel-header{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1rem}.panel-header h3{margin:0;font-size:1.05rem;letter-spacing:-.02em}.panel-header p{margin:.25rem 0 0;color:var(--muted);font-size:.86rem}.section-kicker{color:var(--subtle);font-size:.74rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.table-wrap{width:100%;overflow-x:auto;border:1px solid var(--border);border-radius:10px}table{width:100%;min-width:620px;border-collapse:collapse;text-align:left}caption{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}th,td{padding:.8rem .85rem;border-bottom:1px solid rgba(38,54,80,.72);vertical-align:top}th{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;font-weight:800;background:rgba(27,41,64,.55)}td{font-size:.88rem}tr:last-child td{border-bottom:0}.mono{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;font-size:.78rem;overflow-wrap:anywhere}.muted{color:var(--muted)}.subtle{color:var(--subtle)}.badge{display:inline-flex;align-items:center;gap:.35rem;border:1px solid var(--border);border-radius:999px;padding:.22rem .5rem;font-size:.72rem;font-weight:800;text-transform:capitalize}.badge-success{color:#8ce8bd;background:rgba(87,214,160,.1);border-color:rgba(87,214,160,.3)}.badge-warning{color:#f4d995;background:rgba(240,198,116,.1);border-color:rgba(240,198,116,.3)}.badge-danger{color:#ffabb4;background:rgba(255,125,139,.1);border-color:rgba(255,125,139,.3)}.badge-neutral{color:#b8c7e4;background:rgba(154,169,196,.08)}.empty-state{padding:2rem 1rem;text-align:center;color:var(--muted);border:1px dashed var(--border);border-radius:10px}.empty-state strong{display:block;color:var(--text);margin-bottom:.25rem}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.form-grid.three{grid-template-columns:1.1fr 1.6fr auto}.field{display:grid;gap:.35rem}.field label{color:var(--muted);font-size:.78rem;font-weight:700}.field input{width:100%;min-height:44px;background:#0c1424;color:var(--text);border:1px solid #334766;border-radius:9px;padding:.65rem .75rem}.field input::placeholder{color:#71809c}.form-actions{display:flex;align-items:end;gap:.5rem;flex-wrap:wrap}.notice{display:none;margin:.8rem 0;padding:.75rem .85rem;border-radius:9px;border:1px solid var(--border);font-size:.86rem}.notice.show{display:block}.notice-success{color:#9aefc8;background:rgba(87,214,160,.08);border-color:rgba(87,214,160,.28)}.notice-error{color:#ffabb4;background:rgba(255,125,139,.08);border-color:rgba(255,125,139,.28)}.notice-info{color:#b9ceff;background:rgba(124,164,255,.08);border-color:rgba(124,164,255,.28)}.key-reveal{display:none;margin-top:1rem;padding:1rem;background:#0b1424;border:1px solid rgba(240,198,116,.4);border-radius:10px}.key-reveal.show{display:block}.key-reveal code{display:block;margin:.55rem 0;color:#f4d995;overflow-wrap:anywhere;user-select:all}.inline-actions{display:flex;gap:.45rem;align-items:center;flex-wrap:wrap}.toolbar{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap}.list-stack{display:grid;gap:.6rem}.mini-card{padding:.75rem;border:1px solid var(--border);border-radius:10px;background:rgba(27,41,64,.4)}.mini-card strong{display:block}.mini-card span{color:var(--muted);font-size:.82rem}.toast{position:fixed;right:1.25rem;bottom:1.25rem;z-index:30;max-width:min(380px,calc(100vw - 2rem));padding:.8rem 1rem;background:var(--surface-3);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow);color:var(--text);opacity:0;transform:translateY(8px);pointer-events:none;transition:opacity .2s ease,transform .2s ease}.toast.show{opacity:1;transform:none}.visually-hidden{display:none!important}@media(max-width:1050px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.section-grid{grid-template-columns:1fr}}@media(max-width:760px){.topbar{min-height:68px}.brand{min-width:0}.brand-subtitle{display:none}.nav-toggle{display:inline-flex;order:-1}.topbar-spacer{display:none}.user-chip{margin-left:auto}.layout{display:block;padding-top:1rem}.sidebar{position:fixed;inset:68px auto 0 0;z-index:9;width:min(280px,86vw);padding:1.25rem;background:#0d1626;border-right:1px solid var(--border);transform:translateX(-105%);transition:transform .2s ease;box-shadow:var(--shadow)}.sidebar.open{transform:none}.content{padding-top:.5rem}.page-header{display:block}.last-updated{display:block;margin-top:.75rem}.form-grid,.form-grid.three{grid-template-columns:1fr}.metric-grid{gap:.65rem}.metric-card{padding:.85rem}.metric-value{font-size:1.3rem}.panel{padding:.9rem}.section-grid{gap:.75rem}.topbar .status-chip{font-size:0}.topbar .status-chip .status-dot{margin:0}.toolbar .button-secondary{width:100%}}@media(max-width:430px){.brand-title{font-size:.9rem}.metric-grid{grid-template-columns:1fr 1fr}.metric-label{font-size:.68rem}.metric-detail{font-size:.7rem}.metric-value{font-size:1.15rem}th,td{padding:.68rem .65rem}.toast{right:1rem;bottom:1rem}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to main content</a>
<div class="app-shell">
<header class="topbar">
<button id="nav-toggle" class="nav-toggle" type="button" aria-controls="sidebar" aria-expanded="false"><span aria-hidden="true">☰</span><span class="sr-only">Open navigation</span></button>
<div class="brand"><div class="brand-mark" aria-hidden="true">G</div><div><span class="brand-title">GreyAI Control Room</span><span class="brand-subtitle">Operations, safety, and developer access</span></div></div>
<div class="topbar-spacer"></div>
<div id="connection" class="status-chip" role="status" aria-live="polite"><span class="status-dot" aria-hidden="true"></span><span id="status">Connecting</span></div>
<div id="user-summary" class="user-chip">Checking session…</div>
</header>
<div class="layout">
<aside id="sidebar" class="sidebar" aria-label="Dashboard navigation">
<p class="nav-label">Workspace</p>
<nav class="nav-list">
<button class="nav-button" type="button" data-section="overview" aria-current="true"><span class="nav-icon" aria-hidden="true">01</span>Overview</button>
<button class="nav-button" type="button" data-section="referrals"><span class="nav-icon" aria-hidden="true">02</span>Referrals</button>
<button id="developer-nav" class="nav-button" type="button" data-section="developer" hidden><span class="nav-icon" aria-hidden="true">03</span>Developer</button>
<button id="admin-nav" class="nav-button" type="button" data-section="admin" hidden><span class="nav-icon" aria-hidden="true">04</span>Administration</button>
</nav>
<div class="sidebar-footer"><div class="section-kicker">Session</div><a href="/logout">Sign out</a></div>
</aside>
<main id="main-content" class="content" tabindex="-1">
<section id="overview" class="page-section" aria-labelledby="overview-title">
<div class="page-header"><div><p class="eyebrow">Live workspace</p><h1 id="overview-title">Operational overview</h1><p>See what GreyAI is doing now, how the platform is performing, and where attention is needed.</p></div><div id="last-updated" class="last-updated">Waiting for first refresh…</div></div>
<div class="metric-grid" aria-label="Platform summary"><div class="metric-card"><span class="metric-label">Service</span><strong id="service-metric" class="metric-value">Connecting</strong><span class="metric-detail">Public health state</span></div><div class="metric-card"><span class="metric-label">Your role</span><strong id="role" class="metric-value">—</strong><span class="metric-detail">Current access level</span></div><div class="metric-card"><span class="metric-label">Operations</span><strong id="count" class="metric-value">0</strong><span class="metric-detail">Visible recent operations</span></div><div class="metric-card"><span class="metric-label">Queue</span><strong id="queue-metric" class="metric-value">—</strong><span class="metric-detail">Current work waiting</span></div></div>
<div class="section-grid"><article class="panel"><div class="panel-header"><div><h2>Recent execution</h2><p>Latest browser, chat, download, and automation activity.</p></div><span class="section-kicker">Auto-refresh</span></div><div id="ops" aria-live="polite"><div class="empty-state"><strong>Loading operations</strong><span>Keeping the current view up to date.</span></div></div></article><article class="panel"><div class="panel-header"><div><h2>Platform notes</h2><p>Operational messages and recovery guidance.</p></div></div><div id="platform-note" class="list-stack"><div class="mini-card"><strong>Secure session</strong><span>Your dashboard session and CSRF token are checked server-side.</span></div><div class="mini-card"><strong>Freshness</strong><span>Data refreshes in the background without replacing the page.</span></div><div class="mini-card"><strong>Need help?</strong><span>Use the Telegram bot for account, automation, and support actions.</span></div></div></article></div>
</section>
<section id="referrals" class="page-section" aria-labelledby="referrals-title"><div class="page-header"><div><p class="eyebrow">Growth</p><h2 id="referrals-title">Referral activity</h2><p>Track your referral code, progress, and qualified rewards without reading raw database output.</p></div></div><div id="referral-summary" class="metric-grid"><div class="metric-card"><span class="metric-label">Referral code</span><strong id="referral-code" class="metric-value">—</strong><span class="metric-detail">Share from Telegram</span></div><div class="metric-card"><span class="metric-label">Pending</span><strong id="referral-pending" class="metric-value">0</strong><span class="metric-detail">Awaiting qualification</span></div><div class="metric-card"><span class="metric-label">Qualified</span><strong id="referral-qualified" class="metric-value">0</strong><span class="metric-detail">Completed referrals</span></div><div class="metric-card"><span class="metric-label">Rewards</span><strong id="referral-rewards" class="metric-value">0</strong><span class="metric-detail">Reward units earned</span></div></div><article id="admin-referrals-panel" class="panel" hidden><div class="panel-header"><div><h3>All referral activity</h3><p>Administrator view of recent referral records.</p></div></div><div id="adminreferrals"></div></article></section>
<section id="developer" class="page-section" aria-labelledby="developer-title" hidden><div class="page-header"><div><p class="eyebrow">Integrations</p><h2 id="developer-title">Developer workspace</h2><p>Create narrowly scoped keys for approved integrations. The secret is shown once and is never stored in readable form.</p></div></div><div class="metric-grid"><div class="metric-card"><span class="metric-label">Active keys</span><strong id="active-keys" class="metric-value">0</strong><span class="metric-detail">Currently usable</span></div><div class="metric-card"><span class="metric-label">Requests, 24h</span><strong id="requests-24h" class="metric-value">0</strong><span class="metric-detail">All active keys</span></div><div class="metric-card"><span class="metric-label">Denied, 24h</span><strong id="denied-24h" class="metric-value">0</strong><span class="metric-detail">Policy or rate-limit denials</span></div><div class="metric-card"><span class="metric-label">API scope</span><strong class="metric-value">check</strong><span class="metric-detail">Current public endpoint</span></div></div><article class="panel"><div class="panel-header"><div><h3>API keys</h3><p>Use descriptive names so each integration is easy to identify and revoke.</p></div><a href="/api/v1/docs" target="_blank" rel="noreferrer">Read API contract</a></div><div id="developer-notice" class="notice" role="status"></div><form id="create-key-form" class="form-grid three"><div class="field"><label for="keyname">Key name</label><input id="keyname" name="keyname" maxlength="80" placeholder="e.g. stock-monitor" required></div><div class="field"><label for="keyscope">Scopes</label><input id="keyscope" name="keyscope" value="check" placeholder="check" required></div><div class="form-actions"><button class="button-primary" type="submit">Create key</button></div></form><div id="key-reveal" class="key-reveal" role="alert"><strong>Copy this key now — it will not be shown again.</strong><code id="new-key"></code><button id="copy-key" class="button-secondary" type="button">Copy key</button></div><div class="table-wrap" style="margin-top:1rem"><table><caption>Developer API keys</caption><thead><tr><th>Name</th><th>Key ID</th><th>Scope</th><th>Status</th><th>Last used</th><th>Action</th></tr></thead><tbody id="developerkeys"><tr><td colspan="6"><div class="empty-state">Loading keys…</div></td></tr></tbody></table></div><form id="revoke-key-form" class="form-grid three" style="margin-top:1rem"><div class="field"><label for="revokeid">Key ID to revoke</label><input id="revokeid" name="revokeid" placeholder="key_…" required></div><div></div><div class="form-actions"><button class="button-danger" type="submit">Revoke key</button></div></form></article></section>
<section id="admin" class="page-section" aria-labelledby="admin-title" hidden><div class="page-header"><div><p class="eyebrow">Restricted workspace</p><h2 id="admin-title">Administration</h2><p>Review platform signals and take deliberate, auditable account actions.</p></div></div><div class="metric-grid"><div class="metric-card"><span class="metric-label">Suspicious users</span><strong id="suspicious-count" class="metric-value">0</strong><span class="metric-detail">Currently surfaced for review</span></div><div class="metric-card"><span class="metric-label">Banned users</span><strong id="banned-count" class="metric-value">0</strong><span class="metric-detail">Current account state</span></div><div class="metric-card"><span class="metric-label">Top users</span><strong id="top-users-count" class="metric-value">0</strong><span class="metric-detail">Usage leaders returned</span></div><div class="metric-card"><span class="metric-label">Most risky</span><strong id="risk-count" class="metric-value">0</strong><span class="metric-detail">Conservative review queue</span></div></div><article class="panel"><div class="panel-header"><div><h3>User lookup</h3><p>Search by Telegram ID or username, then select a result for moderation.</p></div></div><form id="user-search-form" class="form-grid three"><div class="field"><label for="userq">Telegram ID or username</label><input id="userq" name="userq" placeholder="6411860985 or @username" required></div><div></div><div class="form-actions"><button class="button-primary" type="submit">Search user</button></div></form><div id="users" style="margin-top:1rem"><div class="empty-state"><strong>No search yet</strong><span>Search results will appear here.</span></div></div></article><article class="panel"><div class="panel-header"><div><h3>Account action</h3><p>Actions are protected by CSRF, role checks, audit logs, and user notifications.</p></div></div><div id="moderation-notice" class="notice" role="status"></div><form id="moderation-form" class="form-grid three"><div class="field"><label for="banid">User ID</label><input id="banid" name="banid" inputmode="numeric" placeholder="User ID" required></div><div class="field"><label for="reason">Reason</label><input id="reason" name="reason" maxlength="500" placeholder="Reason for the action" required></div><div class="form-actions"><button id="ban-button" class="button-danger" type="button">Ban user</button><button id="unban-button" class="button-success" type="button">Unban user</button></div></form></article><div class="section-grid"><article class="panel"><div class="panel-header"><div><h3>Open reports</h3><p>Review reports and record an outcome.</p></div></div><div id="reports"><div class="empty-state">Loading reports…</div></div><form id="report-form" class="form-grid" style="margin-top:1rem"><div class="field"><label for="reportid">Report ID</label><input id="reportid" name="reportid" placeholder="Report ID" required></div><div class="field"><label for="reportresolution">Resolution</label><input id="reportresolution" name="reportresolution" placeholder="Resolution" required></div><div class="form-actions"><button class="button-primary" type="submit">Resolve report</button></div></form></article><article class="panel"><div class="panel-header"><div><h3>Open appeals</h3><p>Give the affected user a clear recorded outcome.</p></div></div><div id="appeals"><div class="empty-state">Loading appeals…</div></div><form id="appeal-form" class="form-grid" style="margin-top:1rem"><div class="field"><label for="appealid">Appeal ID</label><input id="appealid" name="appealid" placeholder="Appeal ID" required></div><div class="field"><label for="appealresolution">Resolution</label><input id="appealresolution" name="appealresolution" placeholder="Resolution" required></div><div class="form-actions"><button class="button-primary" type="submit">Resolve appeal</button></div></form></article></div><article class="panel"><div class="panel-header"><div><h3>Banned users</h3><p>Current banned-account list. Select a user ID above to restore access.</p></div></div><div id="banned-users"><div class="empty-state">Loading banned users…</div></div></article><article class="panel"><div class="panel-header"><div><h3>Referral activity</h3><p>Recent referral records across the platform.</p></div></div><div id="adminreferrals-duplicate"></div></article></section>
</main></div></div>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<script nonce="__GREYAI_CSP_NONCE__">
const csrf=decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('greyai_csrf='))?.split('=')[1]||'');
const FETCH_TIMEOUT_MS=10000;
const el=id=>document.querySelector('#'+id);
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const short=value=>{const text=String(value??'');return text.length>26?text.slice(0,12)+'…'+text.slice(-10):text};
const date=value=>{if(!value)return '—';const parsed=new Date(value);return Number.isNaN(parsed.getTime())?esc(value):parsed.toLocaleString([], {dateStyle:'medium',timeStyle:'short'})};
const badge=value=>{const text=String(value||'unknown').toLowerCase();const tone=['succeeded','active','resolved','delivered','operational'].includes(text)?'success':['failed','banned','denied','dead_letter'].includes(text)?'danger':['running','queued','pending','reviewing','scheduled','degraded'].includes(text)?'warning':'neutral';return '<span class="badge badge-'+tone+'">'+esc(text.replaceAll('_',' '))+'</span>'};
function showNotice(id,message,tone='info'){const node=el(id);if(!node)return;node.textContent=message;node.className='notice show notice-'+tone}
function clearNotice(id){const node=el(id);if(node){node.textContent='';node.className='notice'}}
let toastTimer;
function toast(message,tone='info'){const node=el('toast');node.textContent=message;node.className='toast show';clearTimeout(toastTimer);toastTimer=setTimeout(()=>{node.className='toast'},3500)}
function emptyState(title,detail=''){return '<div class="empty-state"><strong>'+esc(title)+'</strong><span>'+esc(detail)+'</span></div>'}
function setFreshness(){el('last-updated').textContent='Updated '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}
async function fetchJson(url,options={}){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);try{const r=await fetch(url,{credentials:'same-origin',...options,signal:controller.signal});const text=await r.text();let data={};try{data=text?JSON.parse(text):{}}catch(_){data={error:text||'invalid_response'}}if(!r.ok){const error=new Error(data.error||('HTTP '+r.status));error.status=r.status;throw error}return data}finally{clearTimeout(timer)}}
function operationRows(rows){if(!rows.length)return emptyState('No operations yet','New activity will appear here as GreyAI works.');return '<div class="table-wrap"><table><caption>Recent operations</caption><thead><tr><th>Type</th><th>Status</th><th>Target</th><th>Attempts</th><th>Updated</th></tr></thead><tbody>'+rows.map(row=>'<tr><td><strong>'+esc(row.kind||'operation')+'</strong><br><span class="subtle mono">'+esc(short(row.operation_id))+'</span></td><td>'+badge(row.status)+'</td><td class="mono">'+esc(row.target_url||'No target')+'</td><td>'+esc(row.attempt_count??0)+'</td><td>'+date(row.updated_at)+'</td></tr>').join('')+'</tbody></table></div>'}
function renderReferralSummary(ref){const counts=ref&&ref.counts||{};el('referral-code').textContent=ref&&ref.code?short(ref.code):'—';el('referral-pending').textContent=counts.pending??0;el('referral-qualified').textContent=counts.qualified??0;el('referral-rewards').textContent=ref?.reward_units??0}
function referralRows(rows,target='adminreferrals'){const node=el(target);if(!node)return;if(!rows.length){node.innerHTML=emptyState('No referral records','Referral activity will appear when users join through a code.');return}node.innerHTML='<div class="table-wrap"><table><caption>Referral activity</caption><thead><tr><th>Code</th><th>Referrer</th><th>Referred user</th><th>Status</th><th>Created</th></tr></thead><tbody>'+rows.map(row=>'<tr><td class="mono">'+esc(short(row.code))+'</td><td class="mono">'+esc(row.referrer_user_id)+'</td><td class="mono">'+esc(row.referred_user_id)+'</td><td>'+badge(row.status)+'</td><td>'+date(row.created_at)+'</td></tr>').join('')+'</tbody></table></div>'}
function renderKeys(keys){const node=el('developerkeys');if(!keys.length){node.innerHTML='<tr><td colspan="6">'+emptyState('No keys yet','Create a scoped key when you are ready to connect an integration.')+'</td></tr>';return}node.innerHTML=keys.map(key=>'<tr><td><strong>'+esc(key.name)+'</strong></td><td class="mono">'+esc(key.key_id)+'</td><td>'+esc((key.scopes||[]).join(', '))+'</td><td>'+badge(key.status)+'</td><td>'+date(key.last_used_at)+'</td><td><button class="button-danger revoke-inline" type="button" data-key-id="'+esc(key.key_id)+'">Revoke</button></td></tr>').join('');document.querySelectorAll('.revoke-inline').forEach(button=>button.addEventListener('click',()=>{el('revokeid').value=button.dataset.keyId;el('revoke-key-form').requestSubmit()}))}
function renderUsers(users){const node=el('users');if(!users.length){node.innerHTML=emptyState('No matching users','Try a Telegram ID or a username without extra punctuation.');return}node.innerHTML='<div class="table-wrap"><table><caption>User search results</caption><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Plan</th><th>Risk</th><th>Last seen</th><th>Action</th></tr></thead><tbody>'+users.map(user=>'<tr><td><strong>'+esc(user.display_name||user.username||user.telegram_user_id)+'</strong><br><span class="subtle mono">'+esc(user.telegram_user_id)+(user.username?' · @'+esc(user.username):'')+'</span></td><td>'+esc(user.role)+'</td><td>'+badge(user.status)+'</td><td>'+esc(user.plan)+'</td><td>'+esc(user.risk_score??0)+'</td><td>'+date(user.last_seen_at)+'</td><td><button class="button-secondary select-user" type="button" data-user-id="'+esc(user.telegram_user_id)+'">Select</button></td></tr>').join('')+'</tbody></table></div>';document.querySelectorAll('.select-user').forEach(button=>button.addEventListener('click',()=>{el('banid').value=button.dataset.userId;el('reason').focus();toast('User selected for account action')}))}
function renderReports(rows){const node=el('reports');if(!rows.length){node.innerHTML=emptyState('No open reports','The review queue is clear.');return}node.innerHTML='<div class="list-stack">'+rows.map(row=>'<button class="mini-card select-report" type="button" data-report-id="'+esc(row.report_id)+'"><strong>'+esc(row.category||'Report')+' · <span class="mono">'+esc(short(row.report_id))+'</span></strong><span>'+esc(row.description||'No description')+'</span><span class="subtle">Opened '+date(row.created_at)+'</span></button>').join('')+'</div>';document.querySelectorAll('.select-report').forEach(button=>button.addEventListener('click',()=>{el('reportid').value=button.dataset.reportId;el('reportresolution').focus();toast('Report selected for resolution')}))}
function renderAppeals(rows){const node=el('appeals');if(!rows.length){node.innerHTML=emptyState('No open appeals','The appeal queue is clear.');return}node.innerHTML='<div class="list-stack">'+rows.map(row=>'<button class="mini-card select-appeal" type="button" data-appeal-id="'+esc(row.appeal_id)+'"><strong>Appeal · <span class="mono">'+esc(short(row.appeal_id))+'</span></strong><span>'+esc(row.message||'No message')+'</span><span class="subtle">User '+esc(row.user_id)+' · Opened '+date(row.created_at)+'</span></button>').join('')+'</div>';document.querySelectorAll('.select-appeal').forEach(button=>button.addEventListener('click',()=>{el('appealid').value=button.dataset.appealId;el('appealresolution').focus();toast('Appeal selected for resolution')}))}
function renderBanned(users){const node=el('banned-users');el('banned-count').textContent=users.length;if(!users.length){node.innerHTML=emptyState('No banned users','No accounts are currently banned.');return}node.innerHTML='<div class="table-wrap"><table><caption>Banned users</caption><thead><tr><th>User</th><th>Reason</th><th>Updated</th><th>Action</th></tr></thead><tbody>'+users.map(user=>'<tr><td class="mono">'+esc(user.telegram_user_id)+'</td><td>'+esc(user.status_reason||'Administrator action')+'</td><td>'+date(user.updated_at)+'</td><td><button class="button-success select-banned" type="button" data-user-id="'+esc(user.telegram_user_id)+'">Prepare unban</button></td></tr>').join('')+'</tbody></table></div>';document.querySelectorAll('.select-banned').forEach(button=>button.addEventListener('click',()=>{el('banid').value=button.dataset.userId;el('reason').value='Restoring access after administrator review';el('unban-button').focus();toast('Unban action prepared')}))}
function renderAnalytics(data){const suspicious=data.suspicious_users||[];const top=data.top_users||[];const risky=data.most_risky_users||[];el('suspicious-count').textContent=suspicious.length;el('top-users-count').textContent=top.length;el('risk-count').textContent=risky.length}
async function me(){try{const u=await fetchJson('/api/me');el('role').textContent=u.role;el('user-summary').textContent=u.display_name||u.username||('Telegram '+u.telegram_user_id);el('admin').hidden=u.role!=='admin';el('developer').hidden=u.role!=='developer' && u.role!=='admin';el('developer-nav').hidden=u.role!=='developer' && u.role!=='admin';el('admin-nav').hidden=u.role!=='admin';return u}catch(error){el('role').textContent='—';el('service-metric').textContent='Unavailable';el('status').textContent=error.status===401?'Session expired':'Unavailable';el('user-summary').textContent='Session needs attention';el('ops').innerHTML=emptyState(error.name==='AbortError'?'Connection timed out':'Dashboard data could not be loaded','The page will retry automatically.');el('referral-summary').setAttribute('aria-busy','true');if(error.status===401)setTimeout(()=>{location.href='/'},250);throw error}}
async function refresh(){try{const d=await fetchJson('/api/operations'+(el('role').textContent==='admin'?'?scope=all':''));el('count').textContent=d.operations.length;el('ops').innerHTML=operationRows(d.operations);el('service-metric').textContent='Healthy';el('status').textContent='Healthy'}catch(error){el('status').textContent=error.name==='AbortError'?'Timeout':'Degraded';el('service-metric').textContent='Degraded';el('ops').innerHTML=emptyState(error.name==='AbortError'?'Operation refresh timed out':'Operation data is temporarily unavailable','GreyAI will retry without losing this page.')}try{const ref=await fetchJson('/api/referrals');renderReferralSummary(ref)}catch(error){toast(error.name==='AbortError'?'Referral refresh timed out':'Referral data is temporarily unavailable')}setFreshness();return true}
async function developerRefresh(){try{const [stats,keys]=await Promise.all([fetchJson('/api/v1/developer/stats'),fetchJson('/api/v1/keys')]);el('active-keys').textContent=stats.active_keys??0;el('requests-24h').textContent=stats.requests_last_24h??0;el('denied-24h').textContent=stats.denied_events_last_24h??0;renderKeys(keys.keys||[])}catch(error){showNotice('developer-notice',error.name==='AbortError'?'Developer data timed out':'Developer data is temporarily unavailable','error')}}
async function adminRefresh(){if(el('admin').hidden)return;const results=await Promise.allSettled([fetchJson('/api/admin/analytics'),fetchJson('/api/admin/banned'),fetchJson('/api/admin/referrals'),fetchJson('/api/admin/reports'),fetchJson('/api/admin/appeals')]);const [analytics,banned,referrals,reports,appeals]=results;if(analytics.status==='fulfilled')renderAnalytics(analytics.value);if(banned.status==='fulfilled')renderBanned(banned.value.users||[]);if(referrals.status==='fulfilled'){referralRows(referrals.value.referrals||[],'adminreferrals');el('adminreferrals-duplicate').innerHTML=el('adminreferrals').innerHTML}if(reports.status==='fulfilled')renderReports(reports.value.reports||[]);if(appeals.status==='fulfilled')renderAppeals(appeals.value.appeals||[])}
async function adminAction(path,body,noticeId='moderation-notice'){try{await fetchJson(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});showNotice(noticeId,'Action completed and the affected user was notified where applicable.','success');toast('Action completed','success')}catch(error){showNotice(noticeId,error.status===404?'Target was not found.':'Action failed: '+error.message,'error')}finally{await Promise.allSettled([refresh(),adminRefresh()])}}
async function searchUsers(){try{const q=encodeURIComponent(el('userq').value.trim());if(!q){showNotice('moderation-notice','Enter a Telegram ID or username first.','error');return}const d=await fetchJson('/api/admin/users?q='+q);renderUsers(d.users||[])}catch(error){showNotice('moderation-notice','Search failed: '+error.message,'error')}}
async function createKey(){clearNotice('developer-notice');try{const d=await fetchJson('/api/v1/keys',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({name:el('keyname').value.trim(),scopes:el('keyscope').value.split(',').map(value=>value.trim()).filter(Boolean)})});el('new-key').textContent=d.key;el('key-reveal').classList.add('show');showNotice('developer-notice','Key created. Copy it now; the secret will not be available again.','success');el('keyname').value='';await developerRefresh()}catch(error){showNotice('developer-notice','Key creation failed: '+error.message,'error')}}
async function revokeKey(){try{await fetchJson('/api/v1/keys/'+encodeURIComponent(el('revokeid').value.trim()),{method:'DELETE',headers:{'X-CSRF-Token':csrf}});showNotice('developer-notice','Key revoked successfully.','success');el('revokeid').value=''}catch(error){showNotice('developer-notice','Key revocation failed: '+error.message,'error')}finally{await developerRefresh()}}
function bindForms(){el('create-key-form').addEventListener('submit',event=>{event.preventDefault();createKey()});el('revoke-key-form').addEventListener('submit',event=>{event.preventDefault();revokeKey()});el('user-search-form').addEventListener('submit',event=>{event.preventDefault();searchUsers()});el('ban-button').addEventListener('click',()=>adminAction('/api/admin/ban',{user_id:el('banid').value,reason:el('reason').value}));el('unban-button').addEventListener('click',()=>adminAction('/api/admin/unban',{user_id:el('banid').value}));el('report-form').addEventListener('submit',event=>{event.preventDefault();adminAction('/api/admin/reports/'+encodeURIComponent(el('reportid').value),{status:'resolved',resolution:el('reportresolution').value})});el('appeal-form').addEventListener('submit',event=>{event.preventDefault();adminAction('/api/admin/appeals/'+encodeURIComponent(el('appealid').value),{status:'resolved',resolution:el('appealresolution').value})});el('copy-key').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(el('new-key').textContent);toast('Key copied to clipboard','success')}catch(_){toast('Clipboard access was unavailable; select the key text manually')}})}
function bindNavigation(){const sidebar=el('sidebar');el('nav-toggle').addEventListener('click',()=>{const open=sidebar.classList.toggle('open');el('nav-toggle').setAttribute('aria-expanded',String(open))});document.querySelectorAll('[data-section]').forEach(button=>button.addEventListener('click',()=>{const target=el(button.dataset.section);if(!target||target.hidden)return;target.scrollIntoView({block:'start'});document.querySelectorAll('[data-section]').forEach(item=>item.setAttribute('aria-current',String(item===button)));sidebar.classList.remove('open');el('nav-toggle').setAttribute('aria-expanded','false')}))}
async function queues(){if(el('admin').hidden)return;await adminRefresh()}
async function boot(){bindForms();bindNavigation();try{const user=await me();await Promise.allSettled([refresh(),queues()]);if(user.role==='developer'||user.role==='admin'){await developerRefresh();setInterval(()=>developerRefresh().catch(()=>{}),10000)}}catch(_){/* me() rendered the recovery state */}finally{if(el('status').textContent==='Connecting')el('status').textContent='Unavailable';setInterval(()=>refresh().catch(()=>{}),3000);setInterval(()=>queues().catch(()=>{}),10000)}}
boot();
</script>
</body>
</html>"""


async def index_handler(request: web.Request):
    if not _session_from_request(request):
        return web.Response(text="<h1>GreyAI dashboard</h1><p>Open a one-time dashboard link from the Telegram bot.</p>", content_type="text/html")
    nonce = secrets.token_urlsafe(18)
    request["csp_nonce"] = nonce
    return web.Response(text=HTML.replace('__GREYAI_CSP_NONCE__', nonce), content_type="text/html")


def create_dashboard_app() -> web.Application:
    app = web.Application(middlewares=[security_middleware])
    app.add_routes([
        web.get("/", index_handler),
        web.get("/login", login_handler),
        web.get("/logout", logout_handler),
        web.get("/api/me", me_handler),
        web.get("/api/status", public_status_handler),
        web.get("/challenge/{token}", challenge_page_handler),
        web.get("/challenge/{token}/status", challenge_status_handler),
        web.get("/challenge/{token}/screenshot", challenge_screenshot_handler),
        web.post("/challenge/{token}/action", challenge_action_handler),
        web.post("/challenge/{token}/complete", challenge_complete_handler),
        web.post("/challenge/{token}/cancel", challenge_cancel_handler),
        web.get("/api/status/events", public_maintenance_events_handler),
        web.get("/api/health", health_handler),
        web.post("/api/v1/check", api_check_handler),
        web.get("/api/v1/docs", developer_api_docs_handler),
        web.get("/api/v1/keys", developer_keys_handler),
        web.post("/api/v1/keys", developer_key_create_handler),
        web.delete("/api/v1/keys/{key_id}", developer_key_revoke_handler),
        web.get("/api/v1/developer/stats", developer_stats_handler),
        web.get("/api/operations", operations_handler),
        web.get("/api/referrals", referrals_handler),
        web.get("/api/admin/users", admin_users_handler),
        web.get("/api/admin/referrals", admin_referrals_handler),
        web.get("/api/admin/analytics", admin_analytics_handler),
        web.get("/api/admin/runtime", admin_runtime_handler),
        web.get("/api/admin/banned", admin_banned_handler),
        web.get("/api/admin/reports", admin_reports_handler),
        web.get("/api/admin/appeals", admin_appeals_handler),
        web.post("/api/admin/ban", admin_ban_handler),
        web.post("/api/admin/unban", admin_unban_handler),
        web.post("/api/admin/reports/{report_id}", admin_review_report_handler),
        web.post("/api/admin/appeals/{appeal_id}", admin_resolve_appeal_handler),
        web.get("/ws", websocket_handler),
    ])
    return app


async def serve_dashboard() -> None:
    runner = web.AppRunner(create_dashboard_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start()
    while True:
        await asyncio.sleep(3600)
