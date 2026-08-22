"""Authoritative public developer API contract used by the dashboard and GreyAI explanations."""
from __future__ import annotations

import json
from typing import Any

DEFAULT_GREY_PUBLIC_BASE_URL = "https://playwright-tg-mrphatom.fly.dev"
ENABLED_API_SCOPES = ("check",)


def _base_url(base_url: str | None = None) -> str:
    return str(base_url or DEFAULT_GREY_PUBLIC_BASE_URL).strip().rstrip("/")


def developer_api_contract(base_url: str | None = None) -> dict[str, Any]:
    """Return the exact shipped API contract; keep this free of credentials and sessions."""
    base = _base_url(base_url)
    return {
        "name": "GreyAI Developer API",
        "version": "v1",
        "base_url": base,
        "authentication": {
            "scheme": "Bearer",
            "header": "Authorization: Bearer <developer_api_key>",
            "key_format": "gai_live.<key_id>.<secret>",
            "key_management": "Telegram /newkey or the authenticated developer dashboard",
        },
        "enabled_scopes": list(ENABLED_API_SCOPES),
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/check",
                "url": f"{base}/api/v1/check",
                "required_scope": "check",
                "purpose": "Open an allowlisted public webpage and extract a bounded answer.",
                "request": {
                    "content_type": "application/json",
                    "body": {
                        "url": "https://example.com",
                        "extract": "Summarize the important facts on this page.",
                    },
                },
                "response": {
                    "ok": True,
                    "operation_id": "api_<opaque_id>",
                    "title": "Example Domain",
                    "url": "https://example.com",
                    "extracted": ["..."],
                },
            },
            {
                "method": "GET",
                "path": "/api/v1/docs",
                "url": f"{base}/api/v1/docs",
                "authentication": "none",
                "purpose": "Read this redacted machine-readable contract.",
            },
        ],
        "not_enabled": [
            "Bearer-key endpoints for watch, schedule, sessions, login, form filling, or arbitrary Telegram actions.",
            "Direct model-completion endpoints.",
            "Screenshots, cookies, saved sessions, credentials, or unrestricted scraping through /api/v1/check.",
        ],
        "limits": {
            "request_body_bytes": 16384,
            "url_max_characters": 2048,
            "extract_max_characters": 500,
            "server_rate_limit": "per API key, bounded by the account configuration",
            "server_quota": "the owning developer account quota applies",
            "url_policy": "Grey’s existing HTTPS, domain allowlist, SSRF, timeout, queue, and maintenance gates apply",
        },
        "errors": {
            "401": ["api_key_required", "invalid_api_key"],
            "403": ["scope_required"],
            "413": ["request_too_large"],
            "429": ["api_rate_limit_exceeded", "quota_exceeded", "queue_full"],
            "502": ["browser_check_failed"],
            "503": ["maintenance"],
            "504": ["browser_timeout"],
        },
    }


def format_developer_api_example(language: str = "python", base_url: str | None = None) -> str:
    """Return a short, exact integration example for the currently shipped check API."""
    language = str(language or "python").strip().lower()
    base = _base_url(base_url)
    endpoint = f"{base}/api/v1/check"
    if language in {"javascript", "js", "node", "typescript", "ts"}:
        return (
            "<b>GreyAI Developer API — JavaScript</b>\n\n"
            "The shipped API currently exposes one bearer-key operation: <code>POST /api/v1/check</code>. "
            "Your key needs the <code>check</code> scope.\n\n"
            "<pre><code>const response = await fetch("
            f"{json.dumps(endpoint)}, {{\n"
            "  method: \"POST\",\n"
            "  headers: {\n"
            "    \"Authorization\": `Bearer ${process.env.GREY_API_KEY}`,\n"
            "    \"Content-Type\": \"application/json\"\n"
            "  },\n"
            "  body: JSON.stringify({\n"
            "    url: \"https://example.com\",\n"
            "    extract: \"Summarize the important facts on this page.\"\n"
            "  })\n"
            "});\n\n"
            "if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);\n"
            "const result = await response.json();\n"
            "console.log(result.extracted);</code></pre>\n\n"
            "Only the <code>check</code> scope is enabled currently. Watchers, sessions, login, form filling, and arbitrary Telegram actions are not bearer-key API endpoints."
        )
    if language == "curl":
        return (
            "<b>GreyAI Developer API — curl</b>\n\n"
            "<pre><code>curl -X POST "
            f"{endpoint} "
            "\\\n  -H \"Authorization: Bearer $GREY_API_KEY\" "
            "\\\n  -H \"Content-Type: application/json\" "
            "\\\n  -d '{\"url\":\"https://example.com\",\"extract\":\"Summarize the important facts on this page.\"}'</code></pre>\n\n"
            "The response contains <code>ok</code>, <code>operation_id</code>, <code>title</code>, <code>url</code>, and bounded <code>extracted</code> text."
        )
    return (
        "<b>GreyAI Developer API — Python</b>\n\n"
        "The shipped API currently exposes one bearer-key operation: <code>POST /api/v1/check</code>. "
        "Use the exact header <code>Authorization: Bearer &lt;developer_api_key&gt;</code>. Generate a developer key with the <code>check</code> scope, store it in your bot’s secret manager, and never hard-code it.\n\n"
        "<pre><code>import os\nimport requests\n\n"
        f"endpoint = {endpoint!r}\n"
        "headers = {\n"
        "    \"Authorization\": f\"Bearer {os.environ['GREY_API_KEY']}\",\n"
        "    \"Content-Type\": \"application/json\",\n"
        "}\n"
        "payload = {\n"
        "    \"url\": \"https://example.com\",\n"
        "    \"extract\": \"Summarize the important facts on this page.\",\n"
        "}\n\n"
        "response = requests.post(endpoint, json=payload, headers=headers, timeout=100)\n"
        "response.raise_for_status()\n"
        "result = response.json()\n"
        "print(result[\"extracted\"])</code></pre>\n\n"
        "Grey applies the developer account quota, per-key rate limit, HTTPS/domain allowlist, SSRF, queue, timeout, and maintenance controls. The current API does not expose watchers, sessions, login, form filling, screenshots, or arbitrary Telegram actions through bearer keys."
    )
