"""Authenticated operations dashboard for GreyAI.

The dashboard is intentionally small and server-authoritative: it exposes only
redacted metadata and checks role/resource permissions on every request.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from html import escape
from typing import Any, Dict, Optional

from aiohttp import web

from control_plane import (
    admin_ids,
    ensure_user,
    exchange_dashboard_login_token,
    get_dashboard_session,
    get_user,
    is_admin,
    is_developer,
    list_appeals,
    list_operations,
    list_reports,
    list_session_metadata,
    record_admin_action,
    revoke_dashboard_session,
    get_referral_stats,
    list_referrals,
    search_users,
    set_user_status,
    resolve_report,
    resolve_appeal,
    authenticate_api_key,
    check_api_key_rate_limit,
    consume_quota,
    create_api_key,
    list_api_keys,
    revoke_api_key,
    get_developer_stats,
    record_developer_audit,
)

SESSION_COOKIE = "greyai_session"
CSRF_COOKIE = "greyai_csrf"


def _json_rows(rows):
    return [dict(row) for row in rows]


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


def _require_api_key(request: web.Request, required_scope: Optional[str] = None):
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


@web.middleware
async def security_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
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


async def health_handler(request: web.Request):
    session, user = _require_session(request)
    operations = list_operations(None if is_admin(user["telegram_user_id"]) and request.query.get("scope") == "all" else user["telegram_user_id"], 100)
    return web.json_response({"status": "ok", "role": user["role"], "operations": len(operations), "process": {"pid": os.getpid()}})


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

    # Importing inside the handler avoids a bot/dashboard module cycle at startup.
    from bot import COMMAND_TIMEOUT, is_domain_allowed, is_valid_url, run_browser_task_with_retry, task_semaphore

    if not is_valid_url(url) or not is_domain_allowed(url):
        record_developer_audit(None, principal["user_id"], principal["key_id"], "api_check", "denied", {"reason": "url_not_allowed"})
        raise web.HTTPBadRequest(text=json.dumps({"error": "url_not_allowed"}), content_type="application/json")
    allowed_quota, used, limit = consume_quota(principal["user_id"])
    if not allowed_quota:
        record_developer_audit(None, principal["user_id"], principal["key_id"], "api_check", "denied", {"reason": "quota_exceeded"})
        raise web.HTTPTooManyRequests(text=json.dumps({"error": "quota_exceeded", "used": used, "limit": limit}), content_type="application/json")

    operation_id = "api_" + secrets.token_hex(6)
    from bot import create_operation, update_operation
    create_operation(operation_id, principal["user_id"], None, "api_check", url, {"api_key_id": principal["key_id"], "source": "telegram_integration"})
    screenshot_path = None
    try:
        async with task_semaphore:
            result = await asyncio.wait_for(run_browser_task_with_retry(url, [f"ai_extract:{extract}"], principal["user_id"], operation_id), timeout=COMMAND_TIMEOUT + 5)
        screenshot_path = result.get("screenshot")
        return web.json_response({"ok": True, "operation_id": operation_id, "title": str(result.get("title", ""))[:300], "url": url, "extracted": [str(item)[:4000] for item in result.get("extracted", [])[:10]]})
    except asyncio.TimeoutError:
        update_operation(operation_id, "failed")
        raise web.HTTPGatewayTimeout(text=json.dumps({"error": "browser_timeout", "operation_id": operation_id}), content_type="application/json")
    except Exception:
        update_operation(operation_id, "failed")
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
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": "invalid_json"}), content_type="application/json")
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


async def admin_reports_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"reports": _json_rows(list_reports(request.query.get("status", "open"), 100))})


async def admin_appeals_handler(request: web.Request):
    _require_admin(request)
    return web.json_response({"appeals": _json_rows(list_appeals(request.query.get("status", "open"), 100))})


async def admin_ban_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    data = await request.json()
    target_id = int(data.get("user_id"))
    target = get_user(target_id)
    if target and target["role"] == "admin":
        raise web.HTTPForbidden(text=json.dumps({"error": "admin_target_forbidden"}), content_type="application/json")
    ensure_user(target_id)
    reason = str(data.get("reason", "administrator action"))[:500]
    set_user_status(target_id, "banned", reason)
    action_id = record_admin_action(admin["telegram_user_id"], "ban_user", target_id, reason)
    return web.json_response({"ok": True, "action_id": action_id})


async def admin_unban_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    data = await request.json()
    target_id = int(data.get("user_id"))
    set_user_status(target_id, "active", "administrator unbanned user")
    action_id = record_admin_action(admin["telegram_user_id"], "unban_user", target_id, "administrator unbanned user")
    return web.json_response({"ok": True, "action_id": action_id})


async def admin_review_report_handler(request: web.Request):
    session, admin = _require_admin(request)
    _require_csrf(request, session)
    report_id = request.match_info["report_id"]
    data = await request.json()
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
    data = await request.json()
    status = str(data.get("status", "reviewing"))
    resolution = str(data.get("resolution", "reviewed by administrator"))[:4000]
    if not resolve_appeal(appeal_id, admin["telegram_user_id"], status, resolution):
        raise web.HTTPNotFound(text=json.dumps({"error": "appeal_not_found"}), content_type="application/json")
    action_id = record_admin_action(admin["telegram_user_id"], "resolve_appeal", None, resolution, {"appeal_id": appeal_id, "status": status})
    return web.json_response({"ok": True, "action_id": action_id})


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
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GreyAI Operations</title>
<style>body{font-family:system-ui;background:#0b1020;color:#e7ecff;margin:0}main{max-width:1100px;margin:auto;padding:28px}section{background:#131b32;border:1px solid #2d3b63;border-radius:14px;padding:18px;margin:14px 0}h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.metric{background:#0e1630;border-radius:10px;padding:14px}.muted{color:#9aa8cd}code{color:#9bd4ff}button{background:#5c7cfa;color:white;border:0;border-radius:8px;padding:8px 12px;cursor:pointer}input{background:#0e1630;color:white;border:1px solid #3b4c7c;border-radius:8px;padding:8px;margin-right:6px}pre{white-space:pre-wrap;overflow:auto;max-height:420px}</style></head>
<body><main><h1>GreyAI Operations</h1><p class="muted">Live execution, account, and safety control plane</p><div class="grid"><div class="metric">Status<br><strong id="status">connecting</strong></div><div class="metric">Role<br><strong id="role">-</strong></div><div class="metric">Operations<br><strong id="count">0</strong></div></div><section><h2>Execution log</h2><pre id="ops">Loading…</pre></section><section><h2>Referrals</h2><pre id="referrals">Loading…</pre></section><section id="developer" hidden><h2>Developer console</h2><p class="muted">API keys are scoped and shown only once when created.</p><pre id="developerstats">Loading…</pre><pre id="developerkeys">Loading…</pre><p><input id="keyname" placeholder="Key name"><input id="keyscope" value="check" placeholder="Scopes"><button onclick="createKey()">Create key</button></p><p><input id="revokeid" placeholder="Key ID"><button onclick="revokeKey()">Revoke key</button></p></section><section id="admin" hidden><h2>Administrator console</h2><p><input id="userq" placeholder="Telegram ID or username"><button onclick="searchUsers()">Search user</button></p><pre id="users">Search results appear here.</pre><p><input id="banid" placeholder="User ID"><input id="reason" placeholder="Reason"><button onclick="banUser()">Ban</button><button onclick="unbanUser()">Unban</button></p><h3>Referral activity</h3><pre id="adminreferrals">Loading…</pre><h3>Open reports</h3><pre id="reports">Loading…</pre><p><input id="reportid" placeholder="Report ID"><input id="reportresolution" placeholder="Resolution"><button onclick="resolveReport()">Resolve report</button></p><h3>Open appeals</h3><pre id="appeals">Loading…</pre><p><input id="appealid" placeholder="Appeal ID"><input id="appealresolution" placeholder="Resolution"><button onclick="resolveAppeal()">Resolve appeal</button></p></section><p><a href="/logout" style="color:#9bd4ff">Sign out</a></p></main>
<script>
const csrf=decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('greyai_csrf='))?.split('=')[1]||'');
const FETCH_TIMEOUT_MS=10000;
const el=id=>document.querySelector('#'+id);
async function fetchJson(url,options={}){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);try{const r=await fetch(url,{credentials:'same-origin',...options,signal:controller.signal});const text=await r.text();let data={};try{data=text?JSON.parse(text):{}}catch(_){data={error:text||'invalid_response'}}if(!r.ok){const error=new Error(data.error||('HTTP '+r.status));error.status=r.status;throw error}return data}finally{clearTimeout(timer)}}
function showError(id,message){el(id).textContent=message}
async function me(){try{const u=await fetchJson('/api/me');el('role').textContent=u.role;el('admin').hidden=u.role!=='admin';el('developer').hidden=u.role!=='developer';return u}catch(error){el('role').textContent='-';el('status').textContent=error.status===401?'session expired':'unavailable';showError('ops',error.name==='AbortError'?'Dashboard connection timed out. Retrying automatically.':'Dashboard data could not be loaded. Retrying automatically.');showError('referrals','Unavailable until the dashboard session reconnects.');if(error.status===401)setTimeout(()=>{location.href='/'},250);throw error}}
async function refresh(){try{const d=await fetchJson('/api/operations'+(el('role').textContent==='admin'?'?scope=all':''));el('count').textContent=d.operations.length;el('ops').textContent=d.operations.length?JSON.stringify(d.operations,null,2):'No operations yet.'}catch(error){el('status').textContent=error.name==='AbortError'?'timeout':'degraded';showError('ops',error.name==='AbortError'?'Operation refresh timed out. Retrying automatically.':'Operation data is temporarily unavailable. Retrying automatically.');return false}try{const ref=await fetchJson('/api/referrals');el('referrals').textContent=JSON.stringify(ref,null,2)}catch(error){showError('referrals',error.name==='AbortError'?'Referral refresh timed out. Retrying automatically.':'Referral data is temporarily unavailable. Retrying automatically.')}if(el('role').textContent==='admin'){try{const ar=await fetchJson('/api/admin/referrals');el('adminreferrals').textContent=JSON.stringify(ar.referrals,null,2)}catch(error){showError('adminreferrals','Admin referral data is temporarily unavailable.')}}el('status').textContent='healthy';return true}
async function developerRefresh(){try{const s=await fetchJson('/api/v1/developer/stats');el('developerstats').textContent=JSON.stringify(s,null,2);const k=await fetchJson('/api/v1/keys');el('developerkeys').textContent=JSON.stringify(k.keys,null,2)}catch(error){showError('developerstats','Developer data is temporarily unavailable.');showError('developerkeys','Retrying automatically.')}}
async function createKey(){try{const d=await fetchJson('/api/v1/keys',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({name:el('keyname').value,scopes:el('keyscope').value.split(',')})});alert('Copy this key now; it will not be shown again: '+d.key)}catch(error){alert(error.message||'Key creation failed')}finally{await developerRefresh()}}
async function revokeKey(){try{await fetchJson('/api/v1/keys/'+encodeURIComponent(el('revokeid').value),{method:'DELETE',headers:{'X-CSRF-Token':csrf}})}catch(error){alert(error.message||'Key revocation failed')}finally{await developerRefresh()}}
async function searchUsers(){try{const q=encodeURIComponent(el('userq').value);const d=await fetchJson('/api/admin/users?q='+q);el('users').textContent=JSON.stringify(d.users,null,2)}catch(error){showError('users','Search failed: '+error.message)}}
async function adminAction(path,body){try{await fetchJson(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)})}catch(error){alert(error.message||'Action failed')}finally{await refresh()}}
function banUser(){adminAction('/api/admin/ban',{user_id:el('banid').value,reason:el('reason').value})}function unbanUser(){adminAction('/api/admin/unban',{user_id:el('banid').value})}function resolveReport(){adminAction('/api/admin/reports/'+encodeURIComponent(el('reportid').value),{status:'resolved',resolution:el('reportresolution').value})}function resolveAppeal(){adminAction('/api/admin/appeals/'+encodeURIComponent(el('appealid').value),{status:'resolved',resolution:el('appealresolution').value})}
async function queues(){for(const [url,id,key] of [['/api/admin/reports','reports','reports'],['/api/admin/appeals','appeals','appeals']]){try{const d=await fetchJson(url);el(id).textContent=JSON.stringify(d[key],null,2)}catch(error){showError(id,error.status===401||error.status===403?'Not available for this account.':'Queue data temporarily unavailable. Retrying automatically.')}}}
async function boot(){try{const user=await me();await Promise.allSettled([refresh(),queues()]);if(user.role==='developer'){await developerRefresh();setInterval(()=>developerRefresh().catch(()=>{}),10000)}}catch(_){/* me() rendered the recovery state */}finally{if(el('status').textContent==='connecting')el('status').textContent='unavailable';setInterval(()=>refresh().catch(()=>{}),3000);setInterval(()=>queues().catch(()=>{}),10000)}}
boot();
</script></body></html>"""


async def index_handler(request: web.Request):
    if not _session_from_request(request):
        return web.Response(text="<h1>GreyAI dashboard</h1><p>Open a one-time dashboard link from the Telegram bot.</p>", content_type="text/html")
    return web.Response(text=HTML, content_type="text/html")


def create_dashboard_app() -> web.Application:
    app = web.Application(middlewares=[security_middleware])
    app.add_routes([
        web.get("/", index_handler),
        web.get("/login", login_handler),
        web.get("/logout", logout_handler),
        web.get("/api/me", me_handler),
        web.get("/api/health", health_handler),
        web.post("/api/v1/check", api_check_handler),
        web.get("/api/v1/keys", developer_keys_handler),
        web.post("/api/v1/keys", developer_key_create_handler),
        web.delete("/api/v1/keys/{key_id}", developer_key_revoke_handler),
        web.get("/api/v1/developer/stats", developer_stats_handler),
        web.get("/api/operations", operations_handler),
        web.get("/api/referrals", referrals_handler),
        web.get("/api/admin/users", admin_users_handler),
        web.get("/api/admin/referrals", admin_referrals_handler),
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
