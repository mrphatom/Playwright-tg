# Native Grey LLM Integration Plan

## Goal

Make GreyAI’s identity, capability registry, authorization context, durable memory, user awareness, and Agentic continuity native to the application. Gemini remains a replaceable inference provider.

## Dependency order

1. Add a versioned native identity and capability registry in application code.
2. Add deterministic runtime-context builders for Grey, requester, chat, platform, memory, and operation state.
3. Add redaction and context-size guards.
4. Inject the shared native context into chat, intent, media, inline, group, channel, Secretary Mode, and activity-review model calls.
5. Make model-assisted routing validate against the native capability registry and preserve authoritative Agentic receipts.
6. Add bounded active-user and active-operation aggregates without exposing cross-user private data.
7. Add tests for identity, context, permissions, routing, failover, and redaction.
8. Update README and ship through the existing branch/PR/CI/Fly workflow.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Context becomes too large or slow | Per-mode field selection, bounded strings, bounded lists, and explicit token/character limits |
| Model output bypasses policy | Application-side normalization and authorization before execution |
| Cross-user data leakage | Requester/chat scoping and redaction tests; aggregate counts only |
| Native identity drifts across prompts | One registry and one context builder used by every model call |
| Gemini failover loses continuity | Durable context loaded before provider invocation; provider slot is metadata only |
| Native layer creates latency | Deterministic context assembly, no extra network call, low-cost SQLite queries |
| Literal fine-tuning is assumed but unsupported | Keep weight-level tuning as a separate approved follow-up with dataset and evaluation gates |

## Verification checkpoints

- Context builder unit tests pass with owner, admin, developer, and ordinary-user fixtures.
- Prompt tests prove the same Grey identity appears in chat and Agentic interpretation.
- Redaction tests prove secrets and another user’s private data are absent.
- Routing tests prove supported operational requests reach Agentic mode and ordinary explanations remain chat.
- Failover tests prove a provider switch leaves the native context and operation receipt unchanged.
- Full test suite, CI, deployment, and live status verification pass.
