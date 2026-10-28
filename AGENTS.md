# AGENTS.md — rules for every AI agent (Codex, Claude, others)

The repository is the source of truth. Do not rely on chat history.

## Before starting
Read, if present: `AGENTS.md`, `CLAUDE.md`, `README.md`, and everything in `docs/`
(`AI_CONTEXT.md`, `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TODO.md`, `HANDOFF.md`, `NOTES.md`).

## How to work
1. Understand the project, the current task, the latest handoff, and existing style/patterns.
2. Work in small, shippable checkpoints; commit after each working slice.
3. Don't rewrite large parts unless asked. Don't touch unrelated files.
4. Prefer simple, maintainable solutions; follow existing style and architecture.
5. No new dependencies without a clear reason (record it in `docs/DECISIONS.md`).
6. Never commit or print secrets (tokens, API keys, passwords, private keys). Use `.env` (git-ignored) and keep a `.env.example`.
7. If something is unclear: make a reasonable assumption, write it down, continue. Stop only if the missing info is critical.
8. Before changing things, briefly state the plan. After, summarize: what changed, files changed, problems/blockers, next step.

## Shared brain maintenance
- After every meaningful task, update `docs/HANDOFF.md` (goal, changes, files, decisions, blockers, next task).
- Record important technical/product/workflow decisions in `docs/DECISIONS.md`.
- Keep `docs/TODO.md` current.
- Always leave the repo so the next agent can continue from `AGENTS.md` + `docs/HANDOFF.md` + `docs/DECISIONS.md`.
