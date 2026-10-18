# Hand-off: our Music Assistant fork

## Background

This is our fork of [Music Assistant
server](https://github.com/music-assistant/server). We run it ourselves, and
it carries features upstream doesn't have and won't take:

- **`play_events`**: a per-play record of starts, finishes and skips, so
  repeat counts and skip rates can be queried. Upstream keeps only `playlog`,
  which is one row per item, overwritten in place.
- **Background audio analysis on WebDAV and cloud filesystem libraries.**
  Upstream analyses local filesystem providers only.
- **The `ytmusic_free` provider**
  ([sproft/ytmusic-free-provider](https://github.com/sproft/ytmusic-free-provider),
  MIT). It plays YouTube Music without a Premium subscription, which is
  against upstream's usage policy. It will never be upstreamed.
- **Image extras:** `app_secrets.json` and the Widevine CDM, both copied from
  upstream's official image so that providers which need them work.

None of those are in the tree yet. The fork was rebuilt on 2026-10-16 and
they are the work items still to do (see [Work items](#work-items-in-order)).

### Why it was rebuilt

Until 2026-10-11 the fork was a mess:

- Our work was split between `dev` and `stable`.
- `dev` merged upstream's moving `dev` branch by hand and then stopped; it is
  539 commits behind.
- A cron job on hermes.lan merged upstream's `stable` straight into ours, with
  no PR. That job has been removed.
- Upstream's CI was still in the fork.
- There were no fork releases and no fork docs.

So the fork was rebuilt from upstream's stable release `2.10.6`: `upstream`
and `main` were created, the fork's own docs, tooling and CI were added, and
the old history was kept as `archive/*` tags (see [What you're
given](#what-youre-given)). Our features are re-added as fresh commits on
`main`, one work item at a time.

## What you're given

- **Upstream:** `music-assistant/server`. **We follow stable releases only:**
  tags that are exactly `X.Y.Z`, never `X.Y.ZbN` or `X.Y.Z.devN`. `main` is
  currently built on **`2.10.6`**.
- **The old fork**, for reference only, as `archive/*` tags:
  - `archive/dev`: `play_events` is `1b7fd2529`. Background analysis is
    `dc3960a41`, `28943cf15`, `6db33d8b3`, `1664495b8`, `0577112c1` and
    `c01f137d3`. `ytmusic_free` is `8d40d2548`. The Dockerfile extras are
    `d3bc9f02d` and `49d9dfb1a`. The old release workflow is `97864a0d6` and
    the `fix:` commits after it.
  - `archive/stable`: `play_events` again, as `d9f84a131`.
  - `origin` has no branch left but `main` and `upstream`; the rest are only
    these tags.
- **The `forking` skill** (a released unit on hermes.lan). It is the standard
  this repo follows; Spiri's Pinwheel (`spiri-robotics/pinwheel`) is its
  worked example.
- **The fork's own tools**, in `tools/`: `import-upstream` (below),
  `release-version` (below) and `check-guards` (what the `guards` workflow
  runs: upstream's CI and dependabot config must not come back).

## Ground rules

- **`main` is the fork. `upstream` holds upstream's history only,** up to the
  newest stable tag we've imported. Nothing of ours goes on `upstream`.
- **Upstream reaches `main` only by merging `upstream` in a PR, with a merge
  commit.** Never squash or rebase it, never `git merge` upstream directly,
  and never use GitHub's "Sync fork".
- **Upstream's CI never runs here.** Everything under `.github/` on `main` is
  ours. `tools/import-upstream` freezes `.github` on imported commits so it
  stays that way, and the `guards` workflow fails if upstream's workflows
  reappear.
- **Never use upstream's `DB_SCHEMA_VERSION` for our own tables.** See the
  first item under [Known leftovers](#known-leftovers).
- Commits use a plain imperative subject that says what changed and a body
  that says why. No conventional-commit prefixes, even though upstream uses
  them.

## Expected state

Build and test it with nix:

```
nix-shell shell.nix          # python 3.14, uv, ffmpeg 7, the compilers
scripts/setup.sh             # creates .venv and installs the dependencies
pytest                       # the whole suite
pre-commit run --all-files   # the linters
```

`scripts/setup.sh`, `.venv` and `pytest` are upstream's own development setup
and are unchanged; `shell.nix` is ours and only provides the system bits
(including ffmpeg 7, which upstream's `devenv.nix` also pins). Python's own
dependencies come from `pyproject.toml` and `requirements_all.txt` through
`uv`, not from nixpkgs.

`VERIFY.md` records what has actually been checked here, and how. Don't read
this file as a claim that something passes; read that one.

## Known leftovers

1. **The old `play_events` migration took upstream's schema number.** It
   bumped `DB_SCHEMA_VERSION` from 58 to 59. Upstream has since used 59 to 63
   for its own migrations (`2.11.0b4` is at 63). If a database were stamped 59
   by us, upstream's v59 step would be skipped when 2.11 lands.
   - The fix is to create `play_events` in `__create_database_tables` with
     `CREATE TABLE IF NOT EXISTS`. That runs on every start, and the schema
     number stays upstream's.
   - It never shipped. As of 2026-10-11 the live server runs a build of
     `c01f137d3`, from before `play_events` was added. Its database is at
     schema 58, the same as `2.10.6`, with no `play_events` table.
2. **The old background-analysis change** moved about 2,600 lines of
   `filesystem_local/__init__.py` into a new `base.py` class. That would
   conflict with every upstream import. Re-do it as a small per-provider
   opt-in flag checked by the analysis gate in
   `controllers/streams/audio_analysis.py`, with no refactor.
3. **`ytmusic_free` was copied in at 1.1.3.** Its repo is at `v1.2.1` and tags
   releases. Install a pinned tag at image build time instead of copying it
   into our tree.
4. **The old images** (`ghcr.io/hermes-3640/music-assistant-server-fork`,
   tagged `:dev`, `:stable` and `:latest` from `dev` builds) are still up.
   Leave them there as a rollback until the new image is running.
5. **Moving to `2.10.6` is a step back in code.** The live build is based on
   upstream's `dev` branch, merged by hand, while `2.10.6` is a stable
   release. Both are at schema 58, so no migration runs. Even so, anything
   `dev` stored that `2.10.6` doesn't know about (config keys, cache) is
   untested until work item 8 runs against a copy.

`VERIFY.md` has the rest of what the fork still cannot show as checked.

## Work items, in order

Items 1 to 4 are done; see `VERIFY.md` for what was checked.

1. ~~Archive.~~ Every branch that was on `origin` is now an `archive/<branch>`
   tag, and a `git bundle --all` was saved to `~/workspace/archive/`.
2. ~~New branches.~~ `upstream` is upstream's history up to `2.10.6`, tagged
   `2.10.6`. `main` is `upstream` plus the fork's own commits. `origin` is the
   fork and `upstream` is `music-assistant/server`; the duplicate
   `hermes-3640` remote is gone.
3. ~~Fork setup on `main`~~: upstream's CI deleted, the README noted,
   `.claude/settings.json`, `shell.nix` and `VERIFY.md` added, and
   `AGENTS.md` and `CLAUDE.md` replaced with the fork's own (`CLAUDE.md` is a
   plain file containing `@AGENTS.md`; upstream's is a symlink).
4. ~~Fork tooling and CI~~: `tools/import-upstream`, `tools/release-version`,
   `tools/check-guards`, and the `tests`, `release`, `import-upstream` and
   `guards` workflows.
5. **Feature: `play_events`,** created without a schema bump (leftover 1).
   Bring its tests over.
6. **Feature: background analysis on WebDAV and cloud filesystems,** as the
   small flag described in leftover 2, with tests.
7. **Image:** `ytmusic_free` from a pinned release (leftover 3), plus
   `app_secrets.json` and Widevine from the official image. Add a guard check
   that fails the build if any of the three is missing.
8. **Verify, then cut over.**
   - Run against a copy of the live `/data` (leftover 5), and check that
     `play_events` gets created and gets rows.
   - Play something through `ytmusic_free`, and analyse a WebDAV library.
   - Then delete every other branch on `origin`. No side branches are carried
     over; they are kept only as archive tags.
   - Finally, switch hearth.lan to the new image (see [Where it
     runs](#where-it-runs)).

## Releases

Every push to `main` that passes the tests is a release.

- **Version:** the upstream release `main` is built on, plus a build number:
  `2.10.6-1` is the commit that brought in `2.10.6`, `2.10.6-2` the next
  commit on `main`'s first-parent line, and so on. It restarts at 1 with each
  import. `tools/release-version` works it out from the nearest plain `X.Y.Z`
  tag.
- **Tag** each release commit `X.Y.Z-N`. Upstream's tags have no `v` prefix,
  so ours don't either.
- **Inside the program,** the version in `pyproject.toml` is
  `X.Y.Z+hermes.N`, which `tools/release-version --pep440` prints. That is a
  valid PEP 440 local version, so it sorts with `X.Y.Z` rather than below it
  the way a `-N` prerelease would.
- **Images** go to `ghcr.io/hermes-3640/music-assistant-server-fork`, for
  amd64 and arm64, tagged `X.Y.Z-N`, `main`, `latest` and `sha-<commit>`. The
  release workflow builds them from upstream's public base image
  (`ghcr.io/music-assistant/base`), pinned in the workflow's
  `BASE_IMAGE_VERSION` to the base upstream's `2.10.6` uses.

## Pulling in upstream releases

The `import-upstream` workflow runs daily (or on demand) and does what
`tools/import-upstream` does: find upstream's newest stable `X.Y.Z` tag,
bring `upstream` up to it as commits that keep their parent's `.github`,
tag it, and open a PR into `main`. If an import PR is already open it moves
that PR up to the new release instead of opening another.

Merge that PR with a merge commit, then fix on `main` whatever the import
broke in our features. Running `tools/import-upstream` by hand does exactly
what the workflow does, and `IMPORT_UPSTREAM_TAG=X.Y.Z` picks a particular
release instead of the newest.

## Where it runs

The only consumer of the image is hearth.lan, a Home Assistant OS host (debug
SSH is `root@hearth.lan -p 22222`).

- It runs as the add-on `8c238fd8_hermes_music_assistant`, from the add-on
  repo `hermes_music_assistant`.
- It pulls `ghcr.io/hermes-3640/music-assistant-server-fork:stable`. The new
  releases don't publish `:stable`, so cutting over means pointing the add-on
  at `:latest` or at a pinned `X.Y.Z-N`.
- The library database is `/data/library.db` inside the add-on container.

## Open questions

- Should a release also bump the add-on repo's version, so Home Assistant
  offers the update? Or is that done by hand on hearth.lan?
