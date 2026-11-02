"""Build deterministic, target-specific offline packages; never upload or install."""
import argparse
import json
import importlib.util
import re
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "content-operations"
_guard_spec = importlib.util.spec_from_file_location("content_path_guard", SOURCE / "scripts/path_guard.py")
path_guard = importlib.util.module_from_spec(_guard_spec)
_guard_spec.loader.exec_module(path_guard)
linked = path_guard.linked


def split_frontmatter(text):
    """Bound metadata by column-zero delimiter lines; preserve surrounding bytes."""
    opening = re.match(r"\A---[ \t]*\r?\n", text)
    if opening is None:
        raise ValueError("Skill frontmatter must start with a complete --- line")
    closing = re.search(r"(?m)^---[ \t]*(?:\r?\n|\Z)", text[opening.end():])
    if closing is None:
        raise ValueError("Skill frontmatter must end with a complete --- line")
    end = opening.end() + closing.start()
    metadata = text[opening.end():end]
    if "\r" in metadata.replace("\r\n", ""):
        raise ValueError("Unsupported frontmatter line ending; use LF or CRLF")
    return text[:opening.end()], metadata, text[end:]


def members(source=SOURCE, target="claude"):
    result = {}
    files = path_guard.source_files(source)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source.name):
        raise ValueError("Unsupported source folder name")
    frontmatter = split_frontmatter((source / "SKILL.md").read_bytes().decode("utf-8"))
    if not re.search(r"^name: " + re.escape(source.name) + r"\r?$", frontmatter[1], re.M):
        raise ValueError("Skill name must match the package folder")
    # The observed importer rejected the original archive without naming a file.
    # This conservative MD/PY/TXT layout passed; official docs also list JSON/YAML.
    # Preserve JSON contents under text names, without claiming a universal ban.
    template_paths = [p.relative_to(source).as_posix() for p in files
                      if p.parent == source / "templates" and p.name.endswith(".template.json")]
    for file in files:
        if "__pycache__" in file.parts or file.suffix == ".pyc":
            continue
        rel = file.relative_to(source)
        parts = rel.parts
        allowed = (str(rel) in {"SKILL.md", "LICENSE"}
                   or (len(parts) == 2 and ((parts[0] == "scripts" and file.suffix == ".py")
                       or (parts[0] == "references" and file.suffix == ".md")
                       or (parts[0] == "templates" and file.name.endswith(".template.json"))
                       or (parts[0] == "agents" and file.name == "openai.yaml"))))
        if not allowed:
            raise ValueError("Unrecognised file in distributable skill; review before packaging")
        data = file.read_bytes()
        if target == "gemini":
            if rel.as_posix() == "agents/openai.yaml":
                continue  # Optional OpenAI display metadata is not a Gemini input.
            if rel.as_posix() == "LICENSE" or parts[0] == "templates":
                rel = Path(rel.as_posix() + ".txt")
            if rel.as_posix() == "SKILL.md":
                # The observed Gemini importer reads a folded YAML indicator
                # literally as the description. Emit an equivalent single line.
                folded = re.search(r"(?m)^description: >-\r?\n((?:(?:[ \t][^\r\n]*|)\r?\n)+)", frontmatter[1])
                if folded:
                    lines = folded.group(1).splitlines()
                    if any(not line.startswith("  ") or not line[2:]
                           or line[2].isspace() for line in lines):
                        raise ValueError("Unsupported folded Gemini description; use equal two-space indentation without blank lines")
                    description = " ".join(line[2:] for line in lines)
                    # JSON double-quoted strings are valid YAML strings: preserve
                    # colon/hash punctuation, literal quotes and scalar-like text.
                    quoted = json.dumps(description, ensure_ascii=False)
                    metadata = (frontmatter[1][:folded.start()] + "description: " + quoted + "\n"
                                + frontmatter[1][folded.end():])
                    data = (frontmatter[0] + metadata + frontmatter[2]).encode("utf-8")
                elif re.search(r"(?m)^description:\s*[>|]", frontmatter[1]):
                    raise ValueError("Unsupported multiline Gemini description; use a single line")
            if file.suffix in {".md", ".py"}:
                for old in template_paths:
                    data = data.replace(old.encode("utf-8"), (old + ".txt").encode("utf-8"))
            if rel.suffix not in {".md", ".py", ".txt"}:
                raise ValueError("Unsupported Gemini upload file type")
            parts = rel.parts
        prefix = PurePosixPath("skills") / source.name if target == "openai" else PurePosixPath(source.name) if target in {"claude", "codex"} else PurePosixPath()
        name = (prefix / PurePosixPath(*parts)).as_posix()
        if name.startswith("/") or any(p in ("..", ".") or ":" in p or "\\" in p for p in PurePosixPath(name).parts):
            raise ValueError("Unsafe archive member")
        if name.casefold() in {p.casefold() for p in result}:
            raise ValueError("Case-colliding archive members")
        result[name] = data
    if target == "openai":
        result["plugin.json"] = path_guard.checked_path(ROOT / "plugin.json").read_bytes()
        result["LICENSE"] = path_guard.checked_path(ROOT / "LICENSE").read_bytes()
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--target", choices=("claude", "codex", "gemini", "openai"), default="claude")
    args = p.parse_args()
    try:
        out = path_guard.checked_path(args.out, new_file=True)
        files = members(target=args.target)
    except (ValueError, OSError) as ex:
        p.error(str(ex))
    out.parent.mkdir(parents=True, exist_ok=True)
    path_guard.checked_path(out, new_file=True)
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(files) or any(archive.read(k) != v for k, v in files.items()):
            raise RuntimeError("Invalid skill archive")
    print(json.dumps({"created": True, "target": args.target, "members": len(files), "host_import_tested": False, "installed": False}))

if __name__ == "__main__":
    main()

