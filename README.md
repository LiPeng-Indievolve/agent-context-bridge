# Agent Context Bridge

**English** | [简体中文](README.zh-CN.md)

Move conversations between **Claude Code and Codex**. Scan local projects, select conversations, and continue with a bounded working context backed by searchable history.

**v0.3 alpha · macOS/Linux · Python 3.11+ · No Python runtime dependencies**

## What it does

- Scan agent history and optional workspace folders.
- Select individual conversations, whole projects, or all matching records.
- Migrate in both directions; Claude → Codex uses a working handoff of at most 48KB by default.
- Preserve full source history and project memories locally for on-demand retrieval.
- Preview changes, verify a real model turn, and archive matched old entries after verification.
- Keep existing source sessions unchanged, with a journal and rollback support.

## Quick start

Install [Codex CLI](https://github.com/openai/codex) first to import into Codex. Sign in to run model verification or continue working.

```sh
git clone https://github.com/LiPeng-Indievolve/agent-context-bridge.git
cd agent-context-bridge
python3 -m bridge serve
```

Open the printed localhost URL. **Scan → select → preview → migrate.**

Add workspace folders with `python3 -m bridge --root /path/to/workspaces serve`.

## Finish the switch

**Exit the old agent window with `/exit`.** A successful import does not move an already-open terminal into the new conversation.

```sh
python3 -m bridge scan
python3 -m bridge migrate --to codex --id SESSION_ID --apply
python3 -m bridge verify MIGRATION_ID                 # actual model call; uses quota
python3 -m bridge finish-switch MIGRATION_ID          # preview old entries
python3 -m bridge finish-switch MIGRATION_ID --apply   # archive confirmed older entries
```

Review the verification answer, then run the exact **`resume_command`** from the result in a fresh shell. Without `--apply`, migration and finish-switch only preview changes. The browser offers the same controls.

If an old entry is still busy, `/exit` its terminal and retry. The tool never kills processes, removes writer locks, or deletes old conversations.

## Important limits

- **Alpha:** Codex → Claude creates native session files, but Claude runtime continuation is not yet verified.
- Images, private reasoning, and execution/branch state are not losslessly replayed. MCP, hooks, plugins, and credentials are not installed.
- `verify` checks continuation using an isolated OpenAI configuration, with executable tools/hooks disabled. It does not validate your business tools or production environment.
- Conversion stays local. Verification and continuation use a model service and its quota. Private history may already contain secrets; review it before sharing.
- Keep the tool and state on local disk. Default state: `~/.local/share/agent-context-bridge`.

[Full usage & recovery](docs/USAGE.md) · [What was verified](docs/VERIFICATION.md) · [Releases](https://github.com/LiPeng-Indievolve/agent-context-bridge/releases)

## Development

```sh
python3 -m unittest discover -s tests -v
```

Contributions welcome. Use synthetic fixtures; never submit private transcripts or credentials.

[MIT License](LICENSE)
