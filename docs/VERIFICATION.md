# Verification

Current release: v0.3 alpha. 44 automated tests pass, and the native import → isolated model turn → matched old-entry archive smoke passes. Historical results and remaining limitations are separated below.

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


## v0.2 context-window regression

The default Claude → Codex path now constructs a UTF-8 handoff no larger than 49,152 bytes, including seed and source links. It prioritizes the latest compact summary and last user task; tool bodies are excluded from model input and retained in a local searchable source archive. Project memory bodies are linked through a private index rather than concatenated.

Synthetic tests cover oversized tool output and memory, multilingual seeds, latest task retention, source-line retrieval, private permissions, empty-source errors, and distinct fingerprints for opt-in full-history archival replay. A stub native importer verifies default staged text <=48KB while the raw history archive remains intact. Full-history mode deliberately remains unbounded and may fail model continuation.

The prior v0.1 synthetic native-import/read checks verified discoverability and conversion, not reliable continuation of multi-million-token histories. Those checks must not be presented as proof that an oversized session can resume a model turn. Actual model continuation evidence is recorded separately when run.

A subsequent local rollout built 26 working sessions from real user histories using bounded private handoffs and verified a completed model turn for each (26/26). This is distinct from format-only tests. Session contents, project names and answer logs remain private and are not in this repository. The largest original history that had failed remote compaction was replaced by a bounded working session, with full history kept for retrieval.


## v0.3 terminal switch regression

Import discovery, a real model turn and finishing the switch are separate states. Synthetic regression tests cover zero exit without a completed turn, mismatched verification targets, busy writer hints, CLI success without persisted archive state, ambiguous native timestamps, stale migration attempts, custom CODEX_HOME quoting and custom-provider rejection. Verification disables executable tool/hook capabilities; the browser shares the same guarded operations.

The matched old entry is archived through the native CLI and its archived state is then checked through read-only native catalog access. Source files and unrelated conversations are preserved. A full native/model integration test passed on synthetic data: a 639,554-byte source produced a 31,011-byte staged context, a real isolated model turn completed, the matched old entry was confirmed archived, and the source hash was unchanged. No private transcripts or credentials are published.

Reproduce with `python3 tools/native_switch_smoke.py --allow-model-call` after signing into Codex. This explicit opt-in uses model quota, creates synthetic native sessions, then archives those test sessions; it never targets unrelated conversations.
