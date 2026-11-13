# Agent Context Bridge

**本地扫描、选择迁移、双向交接 Claude Code ↔ Codex。**

A local-first CLI and browser UI for carrying coding-agent conversations and project background between Claude Code and Codex. No runtime Python dependencies. No Claude account required to read existing local Claude Code histories.

**Status: v0.3 alpha.** macOS and Linux, Python 3.11+. Codex transfers require a recent `codex` CLI with native import support. Paginated source histories also require `thread/items/list`; legacy histories use the verified full-read fallback. Tested locally with Codex CLI 0.168.0 (legacy import compatibility also tested with 0.162.1). Windows is not supported yet.

## Quick start / 快速开始

```sh
git clone https://github.com/LiPeng-Indievolve/agent-context-bridge.git
cd agent-context-bridge
python3 -m bridge serve
```

Open the printed `http://127.0.0.1:PORT/#TOKEN` URL. The UI is loopback-only and has no CDN or external assets. Its URL token protects local API access. Do not share the URL.

1. **扫描**：find local Claude Code / Codex conversations and group/filter by project. Optional workspace roots also find projects without conversations.
2. **选择**：search by title or path; select a project, individual conversations, or all filtered results.
3. **预览**：inspect context files and conversion limits before writing.
4. **迁移**：create fresh destination sessions, retain private local context bundles and a migration journal.
5. **续接**：use the returned `codex resume ID` or `claude --resume ID` command from the project's directory.

To include extra workspaces:

```sh
python3 -m bridge --root /path/to/workspaces --root /another/root serve
```

Explicit roots are scanned to depth 4, skipping dependency/cache directories and directory symlinks. The tool does not silently crawl your entire computer. Native memory-observer sessions are excluded by default; use `--include-observers` if desired. Native Codex archives are not included in this alpha.

Optional install:

```sh
python3 -m pip install .
agent-bridge serve
```

## Finish the switch / 真正切换到新会话

A native import can succeed while an old terminal still points at the oversized original chat. **Exit that old agent with `/exit` before launching the returned `resume_command`.** Do not continue typing into the old window.

```sh
# 1. Import a bounded working context; inspect migration_id and resume_command.
agent-bridge migrate --to codex --id CLAUDE_SESSION_ID --apply
# 2. Explicitly run one real model turn (uses your Codex quota).
agent-bridge verify MIGRATION_ID
# 3. Review the answer file and which old entries will be archived.
agent-bridge finish-switch MIGRATION_ID
# 4. Archive only confirmed matched older entries; never deletes the source.
agent-bridge finish-switch MIGRATION_ID --apply
# 5. Run the exact resume_command from the result in a fresh shell.
```

The browser has the same verification, preview and archive controls. Import results say `ready_to_use: false` until a model turn passes. A transfer status of `completed` only means the files/native import completed. `verify` requires a matching started thread, a completed model turn, a successful process exit, no error events and a nonempty final answer; inspect that answer for actual background accuracy.

Verification runs with an isolated OpenAI configuration: user executable settings, rules, hooks, plugins, apps, MCP tools, shell execution and web search are disabled for this check. Login still comes from the selected `CODEX_HOME`; the user's OpenAI model choice is retained. A custom provider needing user configuration is rejected rather than silently verified against another provider. **This tests conversation continuation, not your business tools, deployment, devices or plugin parity.** Normal continuation keeps your usual configuration.

`finish-switch` is dry-run unless `--apply` is present. It requires a successful verification for the current target and refuses an older working migration when a newer one exists. Only older matching journal entries or native imports with the same source path/hash are candidates. Timestamp ambiguity, unknown local state and active writers are reported as incomplete instead of being treated as success. Busy writer? `/exit` the old terminal, then retry. The command does not kill processes, remove locks, edit native databases, delete histories or archive unrelated Codex chats.

The returned `resume_command` includes the exact working directory and custom `CODEX_HOME` when needed. If your result is still a long full-history archive, create a default working-context migration first. Keep the tool and migration state on local disk; cloud files-on-demand directories can cause read timeouts. The default state directory is local `~/.local/share/agent-context-bridge`.

## CLI

Global flags go **before** the subcommand:

```sh
python3 -m bridge scan
python3 -m bridge preview --to codex --id CLAUDE_SESSION_ID
python3 -m bridge migrate --to codex --id CLAUDE_SESSION_ID --apply
python3 -m bridge migrate --to claude --id CODEX_SESSION_ID --apply
python3 -m bridge migrate --to codex --project /absolute/project/path --apply
python3 -m bridge migrate --to codex --all             # dry-run preview
python3 -m bridge migrate --to codex --all --apply     # all eligible sources
python3 -m bridge migrate --to codex --id CLAUDE_SESSION_ID --full-history --apply  # archival only; can exceed model context
python3 -m bridge prepare --source /path/to/session.jsonl --output /new/private/handoff
python3 -m bridge search --index /new/private/handoff/search-index.jsonl --query "pending task"
python3 -m bridge history
python3 -m bridge rollback MIGRATION_ID
```

Without `--apply`, migration writes nothing. The browser's migration button asks for confirmation. A bulk batch reports errors per session and continues, so successfully finished sessions are retained. Re-run to skip identical completed sources. Source changes create a fresh destination snapshot.

Custom stores and isolated tests:

```sh
python3 -m bridge --claude-home /local/claude --codex-home /local/codex \
  --state-dir /local/bridge-state scan
```

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` are honored. No API key is needed for format conversion; continuing a conversation with a model requires a working target account.

## What is preserved?

| Content | Behavior |
|---|---|
| Claude → Codex (default) | <=48KB working context: latest compact summary and newest plain-text conversation, with latest user task reserved; full history retained in a private source archive + searchable line-number index |
| Full archival replay (`--full-history`) | Opt-in conversion of portable historical messages; may exceed context limits and fail to resume |
| Tool calls and results | Default working context excludes tools; raw source and offline search index retain them. Full-history mode labels them as historical text |
| Project background | Copies project documents and Claude memory into a private bundle. Default CC → Codex links a private context index; relevant files can be read on demand, without loading every memory body into the model |
| Modern Codex history | Reads paginated native items when supported; legacy-only native fallback; refuses unsupported paginated exports rather than silently truncating |
| Images, attachments, private reasoning | Not replayed; unsupported blocks reported |
| MCP, hooks, plugins, credentials | Not installed or migrated |
| Project source code | Stays in its original directory; missing project directories cause an explicit error |
| Global rules / config and inherited rules | Not migrated in this alpha |

This is **portable context migration**, not a lossless clone of a running agent. Imported background is dated historical data; verify old deployment instructions against current code. Large histories must not be replayed into the model all at once. The default bounded working context keeps full history available for local retrieval. Do not assume compaction can rescue an oversized archival import. Native formats and APIs can change.

### Finding migrated conversations

From the project directory, use Codex `/resume`, or `codex resume --all` to search across directories. The exact `codex resume ID` returned by a successful migration is the most reliable entry point. Native import also registers the conversation for desktop discovery, but version-specific desktop behavior should be checked on your installation.

For Claude Code, the tool creates a new native JSONL session with a new UUID. Use `claude --resume ID` from the saved project directory. **Claude runtime continuation has not been verified in this release**; see the verification report. Existing Claude sessions are never edited.

## Context-limit fix in v0.2

v0.1 could import a large history and make it discoverable while the first model continuation failed with `context_window_exceeded`. A visible `/resume` entry alone is not evidence of a usable working session. v0.2 defaults Claude → Codex to a <=48KB UTF-8 working handoff, preserving full source history and searchable original line numbers locally. This is an extractive seed, not a guarantee that every old decision is already in the model context. Use the linked context index and offline search to retrieve more details as needed.

`--full-history` is explicitly archival and can reproduce the v0.1 failure. Bounded and archival transfers have distinct journal fingerprints. Existing v0.1 imports are not silently modified: create a fresh default-mode migration to obtain a bounded working session.

Private runtime state defaults to `~/.local/share/agent-context-bridge`, outside synced Documents/Desktop folders. Keep it there: cloud eviction of referenced archives can make later retrieval fail.

## Safety and recovery

- Existing source histories are never modified. Codex import uses its native app-server; the tool never edits Codex SQLite directly. Codex 0.162.1 requires a temporary new UUID session under the default `~/.claude/projects` for native discovery (even with custom stores). This private staging file is backed up and removed only if unchanged after import. An interrupted process may leave staging behind; inspect the journal before cleanup.
- The journal and backups live at `~/.local/share/agent-context-bridge` (private permissions). They contain conversation text and may contain secrets already present in your history. They are not uploaded by the tool. Continuing in an agent sends context according to that agent's settings.
- A completed identical transfer is skipped. Failed/uncertain native imports are marked for manual recovery rather than blindly retried.
- Claude rollback removes only a newly created file whose hash still matches. A resumed or edited target is protected.
- Codex rollback **archives** the imported thread; it does not delete it. Backups remain.
- Do not run migration against an actively changing source conversation. This alpha does not provide consistent live snapshots of ongoing writes.
- No automatic secret redaction: silent alteration can corrupt technical context. Review histories before sharing them. Never commit your migration state.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q bridge
```

See [verification](VERIFICATION.md) for what was actually tested and its boundaries, and [implementation plan](PLAN.md).

## Design

`scan.py` discovers native stores; `codec.py` normalizes portable messages; `rpc.py` reads/imports native Codex sessions; `handoff.py` prepares bounded contexts and offline indexes; `engine.py` journals additive transfers and rollback; `switching.py` verifies real model continuation and archives only confirmed superseded entries; CLI and local UI share the same engine.

The app uses no third-party migration code. Native Codex API behavior was validated locally. Contributions for version adapters, Windows support, attachment portability, and additional formats are welcome. Please use synthetic fixtures in bug reports; never attach private histories.

## License

MIT.

Runtime metadata-only JSONL files are not conversations and are excluded from the conversation scan.
