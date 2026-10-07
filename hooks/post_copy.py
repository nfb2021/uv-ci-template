"""Post-copy task of uv-ci-template (runs in the destination repo, stdlib only).

1. Adds the dev tools to the project's ``dev`` dependency group (``uv add --dev``),
   so ruff/ty/pytest/pre-commit versions are pinned by ``uv.lock`` and identical in
   git hooks, ``just`` recipes and CI.
2. Installs the git hooks (pre-commit, commit-msg, pre-push) if this is a git repo.
3. Warns about existing configuration that the template's files now shadow.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path.cwd()
ok = True


def warn(msg: str) -> None:
    global ok
    ok = False
    print(f"  ! {msg}")


def run(*cmd: str) -> bool:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-deps", default="")
    args = parser.parse_args()

    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists() and not (ROOT / ".git").exists():
        return  # `copier update` replays templates in scratch dirs: nothing to do there
    print("uv-ci-template: post-copy checks")
    if not pyproject.exists():
        print(
            "  ✗ no pyproject.toml: run `uv init` (or `uv init --package`) first, then `copier update`."
        )
        sys.exit(1)
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    # 1. dev tools, pinned through uv.lock
    if args.dev_deps and not run("uv", "add", "--dev", *args.dev_deps.split()):
        warn("`uv add --dev` failed; add the tools manually: " + args.dev_deps)

    # 2. git hooks (types come from default_install_hook_types in the config)
    if (ROOT / ".git").exists():
        if not run("uv", "run", "--frozen", "pre-commit", "install", "--install-hooks"):
            warn("installing the git hooks failed; run `just hooks` later")
    else:
        warn("not a git repository: run `git init`, then `just hooks`")

    # 3. shadowed or conflicting configuration
    tool = data.get("tool", {})
    shadowed = {
        "ruff": "ruff.toml",
        "ty": "ty.toml",
        "commitizen": ".cz.toml",
    }
    for section, file in shadowed.items():
        if section in tool and (ROOT / file).exists():
            warn(
                f"pyproject.toml has [tool.{section}], but {file} now takes precedence. "
                f"Move any settings you need into {file} and delete [tool.{section}]."
            )
    for legacy in ("setup.cfg", ".flake8", "mypy.ini", ".isort.cfg"):
        if (ROOT / legacy).exists():
            warn(
                f"{legacy} found: ruff/ty replace flake8/isort/mypy; remove it if unused."
            )

    justfiles = [
        p for p in ROOT.iterdir() if p.name.lower() in ("justfile", ".justfile")
    ]
    if len(justfiles) > 1:
        warn("several justfiles found; keep one and make it `import 'ci.just'`.")
    for jf in justfiles:
        if "import 'ci.just'" not in jf.read_text(encoding="utf-8"):
            warn(
                f"{jf.name} exists but does not import the shared recipes: add `import 'ci.just'` at its top."
            )

    print("  ✓ all good" if ok else "  (fix the items above, then rerun `just check`)")


if __name__ == "__main__":
    main()
