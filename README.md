# uv-ci-template

Plug-and-play quality gates for **uv-managed Python repositories**: git hooks, GitHub
Actions, ruff, ty, pytest, Conventional Commits and releases. The same setup works for
a fresh repo and an existing one, and `copier update` rolls changes out to every repo
that uses it. Distilled from [canvodpy](https://github.com/nfb2021/canvodpy)'s CI/CD,
with its gaps fixed (see [Differences from canvodpy](#differences-from-canvodpy)).

Built with [Copier](https://copier.readthedocs.io), which runs through `uvx`, so there is
nothing to install beyond **uv**, **git** and **[just](https://just.systems)**
(`brew install just` / `winget install Casey.Just` / `cargo install just`).

## Use it

```sh
# fresh repo
uv init --package myproj && cd myproj && git init
uvx copier copy --trust gh:nfb2021/uv-ci-template .

# existing repo (needs a pyproject.toml; commit or stash your work first)
cd my-existing-repo
uvx copier copy --trust gh:nfb2021/uv-ci-template .
just check              # first run auto-fixes formatting/imports; review the diff
git add -A && git commit -m "ci: adopt uv-ci-template"

# later: pull in the latest version of the standard
just update-template    # = uvx copier update --trust

# once per GitHub repo, after the first push: require green CI on the default branch
just protect
```

`--trust` lets Copier run [`hooks/post_copy.py`](hooks/post_copy.py), which
1. adds ruff, ty, pytest, pytest-cov, pre-commit (and commitizen) to the project's `dev`
   dependency group with `uv add --dev`, so **uv.lock pins every tool** and hooks, `just`
   and CI always run identical versions;
2. installs the git hooks (pre-commit, commit-msg, pre-push);
3. warns about configuration the template now shadows (`[tool.ruff]`, `[tool.ty]` or
   `[tool.commitizen]` in pyproject.toml, a justfile without `import 'ci.just'`,
   leftover flake8/mypy/isort configs).

### Questions

| Question | Default | Effect |
|---|---|---|
| `project_name` | folder name | release titles |
| `github_owner` | `nfb2021` | CODEOWNERS |
| `python_versions` | `["3.12", "3.13", "3.14"]` | CI test matrix; the first one sets ruff's `target-version` |
| `test_all_os` | yes | test on Ubuntu, macOS *and* Windows |
| `ty_blocking` | yes | no = ty only reports (for adopting on existing code); also drops the pre-push ty hook |
| `line_length` | 88 | ruff |
| `conventional_commits` | yes | commit-msg hook, PR commit check, `just bump`, draft releases on tags |
| `security_scans` | yes | CodeQL and OpenSSF Scorecard (public repos; on private ones CodeQL needs paid GitHub Code Security) |
| `pypi_publish` | no | PyPI publishing via Trusted Publishing when a GitHub release is published |

Answers are stored in `.copier-answers.yml`; change one with
`uvx copier update --trust -d ty_blocking=true`.

## What gets enforced, where

| Check | git hook (local) | `just` | CI (`.github/workflows/ci.yml`) |
|---|---|---|---|
| ruff lint (auto-fix) + ruff format | pre-commit | `lint`, `fmt`, `check` | `hooks` job |
| `uv.lock` matches `pyproject.toml` | pre-commit (`uv-lock`) | `ci` | `hooks` job + `UV_LOCKED=1` on every uv command |
| whitespace, EOF, LF line endings, case conflicts, merge markers, YAML/TOML syntax, files > 1 MB, private keys | pre-commit | `ci` | `hooks` job |
| ty type check | pre-push | `types`, `check` | `types` job |
| Conventional Commit messages | commit-msg | n/a | `commits` job (every commit of a PR) + `pr-title.yml` (the PR title, which becomes the commit on squash merge); Dependabot is configured to write `chore(deps): …` / `ci(deps): …` |
| pytest + coverage | n/a | `test` | `tests` matrix: OS × Python |
| all of the above | | | `ci-ok` (+ `pr-title`): the **required status checks** |

CI runs `pre-commit run --all-files`, so skipping hooks locally (`--no-verify`, or never
installing them) cannot get code past CI. `just protect` creates a GitHub ruleset for
the default branch: PRs only, no force-pushes or deletion, and `ci-ok` (and `pr-title`) must pass
(GitHub enforces rulesets on public repos, or on private repos with a paid plan).

## Files added to a repo

| File | Owned by | Notes |
|---|---|---|
| `.pre-commit-config.yaml` | template | hooks call `uv run --frozen …`, so tool versions come from `uv.lock` |
| `ruff.toml`, `ty.toml`, `.cz.toml` | template | standalone config files, so `pyproject.toml` is never rewritten; they take precedence over `[tool.*]` sections |
| `ci.just` | template | shared recipes |
| `justfile` | repo | created only if missing; just imports `ci.just`, add your own recipes here |
| `.github/actions/setup/action.yml` | template | the only place that pins the uv version for CI |
| `.github/workflows/ci.yml` | template | hooks, ty, commits, tests, ci-ok |
| `.github/workflows/pr-title.yml` | template | PR title must be a Conventional Commit |
| `.github/workflows/release.yml` | template | tag `v*` → draft GitHub release with generated notes |
| `.github/workflows/publish.yml` | template | optional, PyPI Trusted Publishing |
| `.github/workflows/codeql.yml`, `scorecard.yml` | template | optional |
| `.github/dependabot.yml` | template | weekly grouped updates for uv (incl. `uv.lock`), Actions, hooks |
| `.github/ruleset.json`, `.github/CODEOWNERS` | template | used by `just protect` / PR reviews |
| `.gitignore`, `.gitattributes` | repo | created only if missing; `.gitattributes` forces LF on all OSes |

"Owned by template" files are overwritten by `copier update`, so make lasting changes here
in the template. Copier shows a diff and asks before overwriting an existing file.

## Release flow (with `conventional_commits`)

```sh
just bump               # cz bump: version from commit types -> pyproject.toml + uv.lock,
                        # CHANGELOG.md, annotated tag vX.Y.Z
git push --follow-tags  # release.yml drafts a GitHub release; publish it by hand
                        # (with pypi_publish, publishing it triggers publish.yml)
```

## Differences from canvodpy

Checked against canvodpy `main` on 2026-10-07.

| canvodpy | here |
|---|---|
| Three different uv versions: setup action pins 0.10.3, the other workflows take the latest, the `uv-pre-commit` hook uses 0.12.19 | one pinned version, used by the setup action and the hook |
| `just hooks` installs only the pre-commit and commit-msg hooks, so the **ty pre-push hook never runs** | `default_install_hook_types` installs all three |
| whitespace, large-file, private-key and commit-message checks run only locally | CI runs every hook on all files, and checks PR commit messages |
| Dependabot uses the `pip` ecosystem, so `uv.lock` goes stale and workflows run `uv lock` for Dependabot PRs | `uv` ecosystem updates `uv.lock` itself; `UV_LOCKED=1` everywhere |
| `push` (all branches) + `pull_request` triggers, no `concurrency`: every PR commit runs twice | `push` only on `main`, concurrency group cancels superseded runs |
| `canvod-utils` tests missing from the per-package list in `test_platforms.yml` and `just test-all-packages` | one `pytest` call, no hand-maintained lists |
| `[[tool.ty.overrides]]` for two files that `[tool.ty.src] exclude` already skips (dead config) | n/a |
| `just ci`/`testall` use Python 3.13, while `.python-version` and ruff target 3.14 | versions come from one answer |
| local `just check` formats notebooks but CI's format check excludes them | hooks and CI run the same command |
| `permissions: read-all` | `contents: read`; jobs request only what they need |
| no single required check | `ci-ok` aggregates all jobs, for branch rulesets |

## Maintaining the template

Bump `uv_version` and `dev_deps` in [`copier.yml`](copier.yml), the action SHAs in
`template/.github/` and the hook revisions in `template/.pre-commit-config.yaml.jinja`, then
tag a new version (`git tag v0.2.0 && git push --tags`). Repos pick it up with
`just update-template`.
