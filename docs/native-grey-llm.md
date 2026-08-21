# Native Grey LLM Integration Specification

## Objective

GreyAI must behave as a **native Grey system** across ordinary chat, Agentic execution, commands, multimodal input, durable memory, role enforcement, and platform operations. Gemini remains an interchangeable inference provider only; it must not be treated as Grey’s identity, source of truth, command registry, authorization layer, memory store, or execution engine.

Grey’s native layer will assemble a bounded, structured runtime context for every model call. The context will describe Grey’s current identity, capabilities, command and Agentic contracts, platform state, the requesting user’s authorized profile, the relevant Telegram chat scope, durable conversation state, and the current operation state. Application code remains authoritative for authorization, routing, tool execution, payments, roles, quotas, and side effects.

The phrase “train Grey” is interpreted for this release as **native grounding and orchestration**, not unsupported modification of Gemini model weights. A future supervised fine-tuning pipeline may be added separately only with an approved dataset, evaluation set, provider capability, privacy review, and rollback plan.

## Assumptions

1. Grey remains a Python 3.12 Telegram bot using `python-telegram-bot`, Playwright, SQLite, and the existing Gemini failover pool.
2. Existing commands, plan limits, roles, user authorization, Agentic execution, watchers, schedules, moderation, payments, and administrator controls remain behaviorally compatible.
3. The administrator identity is configuration-backed and must never be exposed as a secret or inferred from untrusted text.
4. User awareness is permission-scoped. Grey may know the requesting user’s Telegram ID, display name, username, role, plan, status, quota summary, and authorized activity summaries, but it must not expose private data belonging to other users.
5. Aggregate active-user counts are operational telemetry, not a list of identities. Grey may use bounded counts and activity windows, while user-visible responses disclose only what is appropriate for the requester’s role.
6. Model output is untrusted data. It cannot directly authorize actions, change roles, access hidden prompts, reveal secrets, or execute tools.

## Native Architecture

| Layer | Responsibility | Source of truth |
|---|---|---|
| Grey identity registry | Name, owner label, description, personality modes, supported modalities, limitations, version | Versioned code/config |
| Capability registry | Commands, Agentic modes, scopes, plan gates, confirmation requirements | Application registry |
| Runtime context builder | Per-request identity, user, chat, memory, telemetry, and operation context | Application code + SQLite |
| Native router | Chooses chat, clarification, deterministic command, or Agentic plan | Application code, with model assistance only as bounded classification data |
| Policy gate | Authorization, role, quota, domain, privacy, confirmation, and safety checks | Application code |
| Agent executor | Playwright, watchers, schedules, sessions, notifications, and other side effects | Application code |
| Model adapter | Gemini failover or another future provider; receives native context and returns text/structured data | Provider adapter |
| Durable memory | Conversation turns, reply context, contact logs, operation receipts, and selected user facts | SQLite with owner/chat scoping |
| Observability | Active-user counts, request modes, provider slot, latency, failures, and operation state | Runtime metrics + logs |

## Native Grey Context Contract

Every text, media, inline, group, channel, business, command, and Agentic model call should receive a common structured context envelope. The envelope is assembled in code and serialized into clearly separated sections so untrusted Telegram, webpage, media, and reply text cannot become system instructions.

```json
{
  "schema": "grey.context.v1",
  "grey": {
    "name": "GreyAI",
    "bot_username": "@GreyBrowserBot",
    "description": "Native Grey assistant for conversation and authorized web work",
    "owner_label": "the configured GreyAI owner",
    "identity_source": "application_registry",
    "capability_version": "runtime capability registry version",
    "mode": "chat | agent | command | inline | group | channel | secretary | media",
    "capabilities": [],
    "limitations": [],
    "current_status": "operational | degraded | hard_maintenance | scheduled"
  },
  "requester": {
    "telegram_user_id": 0,
    "username": null,
    "display_name": null,
    "role": "user | developer | admin | future_role",
    "plan": "free | pro | max",
    "account_status": "active | limited | suspended | banned",
    "quota": {"used": 0, "limit": 0, "reset_at": null},
    "authorized_scopes": [],
    "is_owner": false,
    "is_admin": false,
    "is_developer": false
  },
  "chat": {
    "chat_id": 0,
    "chat_type": "private | group | supergroup | channel | inline | business",
    "owner_user_id": 0,
    "business_connection_id_present": false,
    "invocation_scope": "direct | mention | command | inline | secretary"
  },
  "memory": {
    "conversation_turns": [],
    "reply_context": null,
    "contact_summary": [],
    "operation_receipts": [],
    "watcher_context": [],
    "schedule_context": []
  },
  "platform": {
    "active_user_count_window": null,
    "active_operation_count": 0,
    "queue_summary": {},
    "provider_health": "healthy | degraded | unavailable"
  },
  "request": {
    "text": "untrusted user input",
    "media_interpretation": null,
    "untrusted_blocks": [],
    "correlation_id": "operation or request identifier"
  }
}
```

The exact identity, capability, role, and policy data will be generated by deterministic application functions rather than written ad hoc into multiple prompts. The model receives only the fields needed for the current mode, with secrets, raw tokens, cookies, private session content, and other users’ private history excluded.

## Routing and Agentic Continuity

The user-facing abstraction is one Grey conversation. The native router may internally select `chat`, `clarification`, `command`, or `agent`, but the model must never claim that Grey cannot browse or execute a supported task merely because the current call is a chat fallback. The router will:

1. Load the requester, chat scope, reply context, durable memory, and operation receipts.
2. Apply deterministic security and command recognition before model interpretation.
3. Ask the model for a bounded structured intent only when deterministic recognition is insufficient.
4. Normalize and validate the structured result against the native capability registry.
5. Enforce authorization, quota, domain, role, plan, confirmation, and privacy gates in application code.
6. Execute Agentic work through the existing executor and write an authoritative receipt.
7. Feed the receipt back into the next native Grey context so failover keys, restarts, and follow-up messages preserve continuity.
8. Use chat generation only for conversation, explanation, clarification, or a post-execution summary.

The model may suggest a route or plan, but it cannot grant itself capabilities, bypass a gate, or claim a side effect that the executor did not record.

## User and Owner Awareness

Grey should identify the requesting user naturally when the relevant Telegram metadata is available, while avoiding unnecessary repetition of IDs. For example, a private response may use the display name, whereas an administrator audit response may include the numeric Telegram ID. Grey’s owner awareness is represented as a configured ownership relationship and permission flag, not as a prompt claim supplied by the user.

Grey may use bounded operational aggregates such as the number of active users in the last five minutes, active Agentic operations, queue depth, or provider health. It must not expose a user list, private conversation, credentials, or hidden moderation data to ordinary users. Administrators may receive authorized aggregate analytics through existing admin surfaces.

## Durable Native Memory

Conversation turns remain owner-and-chat scoped. Each turn should carry the native mode, operation ID when applicable, provider slot only as non-secret metadata, and a short receipt classification. Contact logs retain bounded metadata and reply relationships. Native facts must be explicit, reviewable, bounded, and redacted; the system must not silently convert arbitrary model output into permanent personal facts.

## Limitations and Honest Behavior

Grey must state when information is unavailable, stale, outside the requester’s permissions, or requires a fresh web operation. It must never claim to have read Telegram history that was not supplied, know the private state of another user, or have performed an Agentic action without a durable application receipt. “Native” means the application owns the identity, context, policy, routing, and memory; it does not mean the external model provider disappears from the inference path.

## Testing Strategy

Tests must cover the context schema, secret and cross-user redaction, owner/admin/developer/user role differences, private/group/channel/inline/business scopes, reply context, failover continuity, chat-to-Agentic routing, deterministic command precedence, unsupported capability refusal, maintenance state, aggregate active-user telemetry, and authoritative execution receipts. Existing bot, platform, and dashboard suites remain mandatory.

## Boundaries

**Always:** Use parameterized SQL, bounded context windows, deterministic authorization, structured intent validation, secret redaction, durable operation receipts, and explicit provider-failure handling.

**Ask first:** Any real model-weight fine-tuning, collection of user data for a training dataset, new persistent personal-memory categories, cross-user analytics exposure, or change to role/owner authorization semantics.

**Never:** Store raw secrets in context, expose private user history, let model output execute unvalidated actions, allow a user prompt to redefine Grey’s identity or owner, claim unsupported capabilities, or bypass Telegram, plan, role, quota, domain, privacy, or confirmation gates.

## Success Criteria

1. Every model call has a native Grey context envelope with the correct requester and chat scope.
2. Chat and Agentic flows share the same identity, memory, policy, and operation receipt contract.
3. Gemini failover changes only the inference provider; it does not erase context or alter Grey’s identity.
4. Grey can accurately describe its commands, capabilities, limitations, plans, roles, and current operational status from the native registry.
5. Grey can use the requester’s authorized name, role, plan, and relevant conversation context without exposing secrets or other users’ private data.
6. Unsupported or unauthorized requests are refused by application policy rather than by a generic model disclaimer.
7. Existing functionality remains green under the full test suite, with new regression coverage for native context and routing.

## Open Question

A literal fine-tuning implementation requires a curated, consented dataset and a provider-supported tuning/evaluation path. This release should first ship the native context and orchestration layer; a separate approved task can add weight-level fine-tuning if desired.
