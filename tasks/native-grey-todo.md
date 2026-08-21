# Native Grey LLM Integration Tasks

- [ ] Add the versioned Grey identity registry and capability registry.
  - Acceptance: one deterministic source describes Grey’s name, owner relationship, descriptions, capabilities, limitations, modes, commands, and plan gates.
  - Verify: registry unit tests and command/capability consistency checks.
  - Files: `bot.py`, `control_plane.py`, `test_bot.py`, `test_platform.py`.

- [ ] Add the bounded native runtime-context builder.
  - Acceptance: every model-facing flow can construct requester-scoped Grey, user, chat, memory, platform, and request context without secrets.
  - Verify: owner/admin/developer/user, group, channel, inline, business, reply, and media fixtures.
  - Files: `bot.py`, `control_plane.py`, tests.

- [ ] Inject the context into chat, intent, media, moderation review, and Agentic planning.
  - Acceptance: provider changes do not change Grey identity or lose durable context.
  - Verify: prompt assertions and failover continuity tests.
  - Files: `bot.py`, tests.

- [ ] Add active-user and active-operation aggregate telemetry.
  - Acceptance: Grey can use bounded counts while ordinary users cannot receive cross-user private data.
  - Verify: role-aware context and redaction tests.
  - Files: `control_plane.py`, `bot.py`, tests.

- [ ] Validate and harden the unified router.
  - Acceptance: supported browser requests reach Agentic mode, ordinary conversation stays chat, and model output cannot grant capabilities or bypass policy.
  - Verify: deterministic routing, malformed model output, unsupported capability, maintenance, quota, and authorization tests.
  - Files: `bot.py`, tests.

- [ ] Update documentation and deploy through the standard PR/CI/Fly workflow.
  - Acceptance: README explains native Grey behavior and the distinction between native orchestration and provider inference.
  - Verify: full test suite, CI, live `/api/status`, and a controlled Telegram smoke test.
  - Files: `README.md`, `docs/native-grey-llm.md`, task files, deployment files only if required.
