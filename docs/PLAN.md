# Agent Context Bridge implementation plan

Goal: local-only selective bidirectional Claude Code/Codex migration with CLI and browser UI.
Architecture: scan native stores, normalize portable messages, write new Claude sessions or use Codex native import; keep source immutable and journal each transfer.
Stack: Python 3.11 standard library, unittest, local HTTP UI.

1. Tests first: scan filtering, portable text/tool conversion, malformed lines, idempotency, changed sources, rollback conflict, HTTP origin/token guards.
2. Implement scanner and codec modules. Discover native roots and optional bounded workspace roots; exclude observer sessions unless requested. Track files and source identities. Preserve tool results as labelled text; report images/thinking loss explicitly.
3. Implement native app-server RPC client. Wait for import completion, check failures and target session. Read modern Codex histories through thread/read when rollouts do not contain messages.
4. Implement transfer engine. Lock journal, stage input outside source, snapshot source hash, create new target only, journal immediately after native success, verify discovery, rollback only unchanged managed files. Context copied into private bundle, never overwrite project instructions automatically.
5. Add CLI scan/preview/migrate/rollback/serve with dry-run default; selectors by ID/project/all and explicit target. Browser exposes same selection and operations, binds localhost with random URL token and Origin/Host checks.
6. Run synthetic tests and isolated native imports in both directions, compare message content and recovery background. Run local inventory smoke test without migrating user sessions.
7. Review diff, compile, package, secret scan tracked files. Create public GitHub repository with MIT license and publish alpha release; no private sessions or workspace inventory in repo.
