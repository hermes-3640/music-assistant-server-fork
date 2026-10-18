# AGENTS.md

This is our fork of [Music Assistant server](https://github.com/music-assistant/server).
Read [`FORK.md`](./FORK.md) before doing anything else: it has the background,
the ground rules, the work list, and how releases and upstream imports work.

## The rules that matter most

- `main` is the fork; `upstream` holds upstream's history only. Upstream
  arrives by merging `upstream` in a PR with a **merge commit** -- never squash
  or rebase it, never `git merge` upstream directly, never use GitHub's "Sync
  fork", and never commit our own work to `upstream`.
- **Upstream's CI never runs here.** Everything under `.github/` on `main` is
  ours. Don't add upstream's workflows back, and don't touch `.github` on
  `upstream` -- `tools/import-upstream` freezes it, and the `guards` workflow
  fails if it comes back.
- Don't bump `DB_SCHEMA_VERSION` for our own tables; that number is
  upstream's. Create our tables with `CREATE TABLE IF NOT EXISTS` in
  `__create_database_tables` instead (leftover 1 in `FORK.md`).
- Commits: a plain imperative subject that says what changed, and a body that
  says why. No conventional-commit prefixes.

## Building

nix-shell shell.nix          # python 3.14, uv, ffmpeg 7, the compilers
scripts/setup.sh             # creates .venv and installs the dependencies
pytest                       # the tests
pre-commit run --all-files   # the linters
