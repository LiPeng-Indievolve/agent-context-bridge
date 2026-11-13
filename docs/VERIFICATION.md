# Verification — v0.1.0 alpha

## Environment

Local execution on macOS with Python 3.11 and Codex CLI 0.162.1. No Claude model login was used. The repository contains only code and synthetic test fixtures.

## Verified

- 17 passing unit/regression tests for scanning, portable message roundtrips, repeated API message IDs, non-object and malformed JSONL records, sidechain/branch loss warnings, native pagination cursor handling, completion notification ordering, idempotence and rollback hash conflicts.
- Isolated synthetic Claude→Codex native import returned completed with no import failures. Native thread read recovered both conversation text and project background.
- Exported that Codex conversation back into a fresh Claude native JSONL session and read back its messages and background.
- Repeated identical native transfer skipped duplicate creation.
- Claude rollback removed only its unchanged generated file. Codex rollback archived the synthetic imported thread.
- Browser: loaded local UI, scanned two synthetic conversations, selected both and displayed dry-run previews with context and loss warnings.
- HTTP checks: missing token and cross-origin requests rejected; authenticated same-origin scan succeeded.
- Python compile passed; wheel built and installed into an isolated virtualenv; installed `agent-bridge --help` passed.

## Native compatibility findings

Codex 0.162.1 exposes `thread/items/list` in its generated schema but the tested app-server returns method-not-found. The adapter uses `thread/read includeTurns:true` **only for legacy histories** and checks full item views. Pagination logic is regression-tested with synthetic API responses. Modern paginated history requires a server that implements the paging API; unsupported export fails explicitly.

The native importer only discovers staged Claude sessions under the default `~/.claude/projects` on this tested version. Custom `CLAUDE_CONFIG_DIR` did not change that behavior. A fresh temporary UUID file is created there and cleaned if unchanged. Existing source session files are not edited.

## Not verified / limitations

- Claude Code model/runtime continuation and its `/resume` picker behavior: no working Claude account was available. The target format and content are tested; runtime support remains experimental.
- Linux matrix runs in GitHub Actions; do not treat local macOS results as Linux runtime verification.
- Newer Codex desktop versions and native format changes require version-specific testing.
- Images, private reasoning and agent internal execution state are not portable. Foreign tools are historical text.
- Live ongoing conversations are not snapshotted transactionally. Stop writing to a source before migrating.
- The earlier real user migration proved native desktop/CLI continuation, but it was a separate manual test before this utility was implemented; it is not claimed as an end-to-end real-data test of this release.
