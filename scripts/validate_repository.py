"""Local repository checks; no network, credentials or external actions."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "content-operations"
errors = []
text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
parts = text.split("---", 2)
if len(parts) != 3 or not text.startswith("---\n"):
    errors.append("Missing YAML frontmatter")
else:
    if not re.search(r"^name: content-operations$", parts[1], re.M):
        errors.append("Wrong skill name")
    if not re.search(r"^description: >-\n  .+", parts[1], re.M):
        errors.append("Expected folded description")
    if len(parts[1]) > 1200:
        errors.append("Frontmatter is unexpectedly large")

for path in SKILL.rglob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
if set(plugin) != {"$schema", "name", "version", "description"} or plugin["$schema"] != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
    errors.append("Unexpected plugin manifest; this package must remain skills-only")
if (SKILL / "LICENSE").read_text(encoding="utf-8").strip() != (ROOT / "LICENSE").read_text(encoding="utf-8").strip():
    errors.append("Packaged licence differs from unchanged repository licence")
for path in ROOT.rglob("*.md"):
    if ".git" in path.parts or "build" in path.parts:
        continue
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if target.startswith(("https:", "http:", "#")):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            errors.append(str(path.relative_to(ROOT)) + ": broken link " + target)

# Inspect only distributable source folders, not ignored local build products.
for folder in (ROOT / "skills", ROOT / "scripts", ROOT / "docs"):
    for path in folder.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in {".jsonl", ".mp4", ".pdf", ".docx", ".pptx", ".xlsx", ".pem", ".key"} or path.name.startswith(".env"):
            errors.append("Unexpected private/binary artefact: " + str(path.relative_to(ROOT)))
        content = path.read_text(encoding="utf-8")
        if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})", content) or re.search(r"^-----BEGIN [A-Z ]*PRIVATE KEY-----$", content, re.M):
            errors.append("Potential credential in " + str(path.relative_to(ROOT)))
for forbidden in ("operations", "evidence"):
    if (ROOT / forbidden).exists():
        errors.append("Populated live-state directory must stay outside repository: " + forbidden)

result = subprocess.run([sys.executable, str(SKILL / "scripts" / "check_records.py"), "--self-test"], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode:
    errors.append(result.stderr or "Record self-test failed")
regression = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], capture_output=True, text=True)
print(regression.stdout.strip())
print(regression.stderr.strip())
if regression.returncode:
    errors.append("Focused regression tests failed")
if errors:
    for error in errors: print("ERROR:", error)
    raise SystemExit(1)
print("PASS: skill contract, JSON, relative links, distribution exclusions and record scenarios.")
