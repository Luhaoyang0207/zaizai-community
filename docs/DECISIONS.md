# Decisions

Format: `D-NNN — date — decision` + why + alternatives considered.

## D-001 — 2026-10-28 — Repo-based shared memory for AI agents
Project memory lives in the repo (`AGENTS.md`, `docs/*`), not in chat history, so Codex, Claude and the owner
can pick up each other's work. `AGENTS.md` holds the rules; `CLAUDE.md` just points to it to avoid two diverging copies.
