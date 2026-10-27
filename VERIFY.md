# What has been checked, and how

What was run, and what it returned. Nothing here is copied from upstream's CI
or assumed. The local checks were run on this machine on 2026-10-16, and the CI
checks were run by GitHub Actions on 2026-10-18 against `main` at `966a7ddbd`;
the run numbers are below. What has *not* been run is in the last section.

Setup: the repo at `/var/lib/hermes/workspace/music-assistant-server-fork`,
`main` = upstream's `2.10.6` (`c24866405bd2068c25a60e1014e5ef8c3f6445bb`, which
is also what upstream's own `stable` branch points at) plus the fork's own
commits, and nothing else.

## Branches

| Check | How | Result |
| --- | --- | --- |
| `upstream` is upstream's history and nothing else | `upstream` created at tag `2.10.6`; `git diff 2.10.6 upstream` | empty |
| `main` adds only the fork's own files | `git diff --name-status 2.10.6 main` | `.github/*`, `.claude/settings.json`, `FORK.md`, `README.md`, `shell.nix`, `tools/*` — no product code touched |
| The fork's release arithmetic | `tools/release-version` at the `2.10.6` commit / at `main`'s tip | `2.10.6-1` / `2.10.6-13` |
| The in-program version | `tools/release-version --pep440` at `main`'s tip | `2.10.6+hermes.13` |
| The imported release tag is on `origin` | `git ls-remote --tags origin 'refs/tags/2.10.6*'` | `2.10.6` (annotated, pointing at `c24866405`) and `2.10.6-13` (pointing at `966a7ddbd`) |

The `2.10.6` tag was created here but not pushed with the rest of the rebuild.
CI works the release version out from the tags it can see, so without it the
release runs called the release `2.10.2+hermes.165`. It is pushed now, and the
`version` job of the release run below agrees with this machine.

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

## The fork's CI

Every push to `main` runs three workflows. The first green run is on `main` at
`966a7ddbd`:

| Workflow | Run | Result |
| --- | --- | --- |
| `guards` | 39133596780 | success |
| `tests` | 39133596790 | success — `14455 passed, 8 skipped, 9 warnings in 462.75s` (7m42s) |
| `release` | 39133596892 | success — the version job, the whole suite, the image build, and the tag |

| Check | How | Result |
| --- | --- | --- |
| Which version CI works out | the release run's `version` job | `2.10.6-13` — the same as `tools/release-version` here |
| The image is published, for both architectures | `gh api /users/hermes-3640/packages/container/music-assistant-server-fork/versions` | one version updated `2026-10-18T14:30:20Z` carrying the tags `2.10.6-13`, `main`, `latest` and `sha-966a7ddbdc1dba0d7ee2460209bc324559ae65d3`, with per-platform child manifests |
| The release commit is tagged | `git ls-remote --tags origin` | `2.10.6-13` -> `966a7ddbd` |

Four things stopped the first pushes, all of them in the fork's own CI and none
of them in the product code. The first three are fixed by the commit that
follows the one this file first described; the fourth is why the first two
release runs failed after their tests had passed:

1. **`lint` never installed `uv`.** Every pre-commit hook runs its tool through
   `scripts/run-in-env.sh`, which is `uv run`, so all 24 hooks died with
   `uv: not found` and the job reported 24 failures without checking anything.
2. **`test` ran pytest as root.** Root ignores file permission bits, so
   `tests/helpers/test_tags.py::test_write_replaygain_track_gain_read_only`
   failed on that alone. Upstream's own test job runs pytest as an
   unprivileged user; ours now does the same.
3. **`publish` did not pass `MASS_VERSION` to the image build.** The Dockerfile
   installs the program from
   `dist/music_assistant-${MASS_VERSION}-py3-none-any.whl`, so the build asked
   for `dist/music_assistant--py3-none-any.whl` and died in the builder. No
   image was pushed and nothing was tagged.
4. **The `2.10.6` tag described above** was missing from `origin`, which is
   what made the release version come out as `2.10.2+hermes.165`.

Skipped by name in `.github/workflows/tests.yml`, with the reason, because they
test what the fork deleted rather than the product:
`tests/scripts/test_release_workflow.py`, `tests/test_generate_release_notes.py`
(upstream's `release.yml`, `auto-release.yml`,
`auto-merge-dependency-updates.yml` and `generate-release-notes` action) and
`tests/scripts/test_check_pr_metadata.py::test_required_items_exist_in_the_real_template`
(`.github/PULL_REQUEST_TEMPLATE.md`). Everything else in the suite runs.

## Repo settings

| Check | How | Result |
| --- | --- | --- |
| The default branch is the fork's branch, not upstream's | `gh repo edit --default-branch main`, then `gh repo view --json defaultBranchRef` | `main` (it was `dev`, which work item 8 deletes) |
| Workflows may open pull requests, which `import-upstream` needs | `gh api repos/.../actions/permissions/workflow` after the update | `{"default_workflow_permissions":"read","can_approve_pull_request_reviews":true}` |

## The image, and what it carries

The fork's image is built from the fork's own git tree, which cannot contain
`app_secrets.json` (upstream generates it from its private appvars repo at
release time) or `widevine_cdm/` (gitignored). `helpers/app_vars.py` resolves
`app_secrets.json` as package data, found nothing, and returned `""` for every
credential — `spotify_client_id` among them, which is why Spotify auth failed.
`0ff896bb4` fixes that by declaring `FROM
ghcr.io/music-assistant/server:2.10.6 AS upstream-extras` and copying
`app_secrets.json` and `/usr/local/bin/widevine_cdm` out of it into the final
image, with a `RUN test -s` guard that fails the build if any of
`app_secrets.json`, `client_id.bin` or `private_key.pem` is missing.
`8ea9b295a` moves the extras image into its own stage; the first attempt died in
BuildKit with `variable expansion is not supported for --from`. Checked on
2026-10-27:

| Check | How | Result |
| --- | --- | --- |
| The release workflow | the `release` run for `8ea9b295a` | success — `version`, `tests.test`, `tests.lint`, `publish` and `tag` |
| The image is published, for both architectures | the run's `publish` job | `ghcr.io/hermes-3640/music-assistant-server-fork:2.10.6-17`, amd64 and arm64 |
| The add-on runs it | the add-on on hearth.lan | `8c238fd8_hermes_music_assistant` updated `2.10.6-15` -> `2.10.6-17`, state `started` |
| The credentials are in the container | inside the running container | `helpers/app_secrets.json` present, 1206 bytes |
| Widevine is in the container | inside the running container | `/usr/local/bin/widevine_cdm/client_id.bin` and `private_key.pem` present |
| The credentials resolve | `app_var("spotify_client_id")` inside the running container | a 32-character string (it was `""` before, which is what broke Spotify auth) |

## Not yet checked

- **The image has run once, by hand.** It builds, publishes and starts on
  hearth.lan, but the add-on was moved to `2.10.6-17` explicitly and does not
  follow the release workflow on its own — that is the cutover, work item 8.
- **`ytmusic_free`**, the rest of work item 7, has not been brought in.
- **Work items 5, 6 and 8**: `play_events`, the background-analysis flag, and
  the cutover. None of them are started.
- **The import workflow running for real** on a day when upstream has cut a new
  stable release. Its script is tested; the workflow's own branch push and the
  PR it opens are not.
