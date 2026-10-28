# Handoff

_Last updated: 2026-10-28 by Claude_

## Current goal
Bootstrap the repository and the shared-memory docs so multiple agents can collaborate.

## What was changed
- Created the shared-brain skeleton: `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore`,
  `docs/HANDOFF.md`, `docs/DECISIONS.md`, `docs/TODO.md`.
- Remote: https://github.com/Luhaoyang0207/zaizai-community (was empty at this point).

## Files changed
All of the above (new).

## Important decisions
See `docs/DECISIONS.md` (D-001).

## Problems / blockers
- No product scope written down yet. `现有的功能.docx` ("existing features") in the repo root is empty (0 bytes).
- Tech stack not chosen (e.g. discord.js vs discord.py, hosting).

## Next recommended task
1. Owner writes the feature list (into `docs/PROJECT_CONTEXT.md`, or fills in the .docx).
2. Choose the bot stack/hosting → record in `docs/DECISIONS.md` and `docs/ARCHITECTURE.md`.
3. Scaffold a minimal bot that connects and replies to one command.
