# What has been checked, and how

What was run, and what it returned. Nothing here is copied from upstream's CI
or assumed: if it is in this file, it was run on this machine on 2026-10-16
against `main` as committed. What has *not* been run is in the last section.

Setup: the repo at `/var/lib/hermes/workspace/music-assistant-server-fork`,
`main` = upstream's `2.10.6` (`c24866405bd2068c25a60e1014e5ef8c3f6445bb`, which
is also what upstream's own `stable` branch points at) plus the fork's own
commits, and nothing else.

## Branches

| Check | How | Result |
| --- | --- | --- |
| `upstream` is upstream's history and nothing else | `upstream` created at tag `2.10.6`; `git diff 2.10.6 upstream` | empty |
| `main` adds only the fork's own files | `git diff --name-status 2.10.6 main` | `.github/*`, `.claude/settings.json`, `FORK.md`, `README.md`, `shell.nix`, `tools/*` — no product code touched |
| The fork's release arithmetic | `tools/release-version` at the `2.10.6` commit / at `main`'s tip | `2.10.6-1` / `2.10.6-10` |
| The in-program version | `tools/release-version --pep440` at `main`'s tip | `2.10.6+hermes.10` |

## The fork's tools

| Check | How | Result |
| --- | --- | --- |
| `tools/import-upstream` end to end | `tools/tests/import-upstream.test.sh` (synthetic upstream with two stable releases and a beta, plus a fork of it with a bare `origin`) | 15/15 checks pass: only stable tags picked; imported commits keep their parent's `.github` and never touch a `.github` path; the release tag records the real upstream commit; authorship kept; upstream's code changes still arrive; re-running changes nothing; history does not double up; merging into `main` leaves `main`'s CI alone and does not bring upstream's back |
| `tools/import-upstream` against the real upstream | `IMPORT_UPSTREAM_URL=https://github.com/music-assistant/server.git`, pushing to a throwaway bare repo | `2.10.6 is already imported.` (exit 0); auto-detection picks `2.10.6` and not `2.11.0b4` or `2.11.0.dev2026101103`; both are refused by name with exit 1 |
| `tools/check-guards` | `tools/check-guards` on `main` | `guards: ok` |
| Shell scripts | `shellcheck 0.11.0` on `tools/release-version`, `tools/import-upstream`, `tools/check-guards`, `tools/tests/import-upstream.test.sh` | clean, no findings |
| Workflows | `actionlint 1.7.12 -no-color .github/workflows/*.yml` (with shellcheck integration) | clean, no findings |

## shell.nix

`nix-shell shell.nix --run '...'`, on a machine with no nixpkgs pin beyond the
channel:

| Check | How | Result |
| --- | --- | --- |
| It evaluates and enters | `nix-shell shell.nix` | ok |
| Python is the version the repo asks for | `python --version` vs `.python-version` (`3.14`) | `Python 3.14.7` |
| The rest of the toolchain is there | `uv --version`, `ffmpeg -version`, `pre-commit --version` | `uv 0.12.17`, `ffmpeg version 7.1.5`, `pre-commit 4.6.2` |
| The preload aiolibdatachannel needs | `echo $LD_PRELOAD` | `.../gcc-15.3.0-lib/lib/libstdc++.so.6` |

## Not yet checked

- **Whether the fork's own CI passes.** The workflows had never run: they start
  with the first push to `main`, which is this commit. `release` calls `tests`,
  so a release only happens if the suite passes.
- **The full pytest suite locally.** Only CI runs it; nothing here has executed
  Music Assistant's tests yet.
- **The Docker image.** The `release` workflow's build has never run, and the
  `ytmusic_free`/`app_secrets.json`/Widevine work (work item 7) has not started.
- **`AGENTS.md` and `CLAUDE.md`.** Still upstream's. Replacing them is part of
  work item 3 and is outstanding: writes to agent-instruction files need a
  person's approval, which this run could not get.
- **That Actions may open pull requests in this repo**, which the
  `import-upstream` workflow needs. Only a repo admin can see that setting.
- **Work items 5 to 8**: `play_events`, the background-analysis flag, the image
  extras, and the cutover to the new image. None of them are started.
- **The import workflow running for real** on a day when upstream has cut a new
  stable release.
