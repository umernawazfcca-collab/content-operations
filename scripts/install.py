"""Additive local skill installation; no network or service changes."""
import argparse
import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "content-operations"
_guard_spec = importlib.util.spec_from_file_location("content_path_guard", SOURCE / "scripts/path_guard.py")
path_guard = importlib.util.module_from_spec(_guard_spec)
_guard_spec.loader.exec_module(path_guard)

def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path_guard.source_files(folder) if "__pycache__" not in p.parts and p.suffix != ".pyc"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=("codex", "claude", "gemini", "both", "all"))
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory; useful for isolated install tests")
    parser.add_argument("--check", action="store_true", help="Inspect without writing")
    args = parser.parse_args()
    args.home = path_guard.checked_path(args.home)
    names = ("codex", "claude") if args.host in ("both", "all") else (args.host,)
    # Gemini also discovers .agents/skills; 'all' uses that one shared copy.
    folders = {"codex": ".agents", "claude": ".claude", "gemini": ".gemini"}
    targets = [args.home / folders[n] / "skills" / SOURCE.name for n in names]
    files = path_guard.source_files(SOURCE)
    if SOURCE / "SKILL.md" not in files:
        parser.error("Source SKILL.md is missing")
    expected = hashes(SOURCE)
    if "codex" in names and path_guard.checked_path(args.home / ".codex/skills" / SOURCE.name).exists():
        parser.error("Legacy .codex copy exists; review the active discovery path before any migration. No files changed.")
    if args.host == "gemini" and path_guard.checked_path(args.home / ".agents/skills" / SOURCE.name).exists():
        targets = [args.home / ".agents/skills" / SOURCE.name]
    if "codex" in names or args.host == "gemini":
        alternate = path_guard.checked_path(args.home / ".gemini/skills" / SOURCE.name)
        if alternate.exists() and (not alternate.is_dir() or hashes(alternate) != expected):
            parser.error("Gemini alias has a differing copy; resolve discovery before installation")
    # Inspect every destination before any writes.
    for target in targets:
        path_guard.checked_path(target)
        if target.exists() and (not target.is_dir() or hashes(target) != expected):
            parser.error("Existing skill differs; no files changed: " + str(target))
    for target in targets:
        if target.exists():
            print("Already identical: " + str(target))
        elif args.check:
            print("Would install: " + str(target))
        else:
            path_guard.checked_path(target, new_file=True)
            shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            if hashes(target) != expected:
                raise RuntimeError("Copy verification failed: " + str(target))
            print("Installed and hash-verified: " + str(target))
    print("No integrations, schedules, messages or plugin settings changed.")

if __name__ == "__main__":
    try:
        main()
    except (path_guard.UnsafePath, OSError) as ex:
        print("Installation refused: " + str(ex), file=sys.stderr)
        raise SystemExit(1)

