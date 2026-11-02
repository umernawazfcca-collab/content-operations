import contextlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile
from test_checks import ROOT, SKILL, temporary_directory, module


def root_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


package = root_module("package")
smoke = module("smoke_test")


class PortabilityTests(unittest.TestCase):
    def command(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / script), *map(str, args)], capture_output=True, text=True)

    def test_each_target_archive_layout_and_extracted_offline_execution(self):
        with temporary_directory() as folder:
            root = Path(folder)
            for target in ("claude", "codex", "gemini", "openai"):
                with self.subTest(target=target):
                    out = root / (target + ".zip")
                    result = self.command("package.py", "--target", target, "--out", out)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(json.loads(result.stdout)["host_import_tested"])
                    second = root / (target + "-again.zip")
                    self.assertEqual(self.command("package.py", "--target", target, "--out", second).returncode, 0)
                    self.assertEqual(out.read_bytes(), second.read_bytes())
                    extracted = root / (target + " espace café")
                    with zipfile.ZipFile(out) as archive:
                        names = archive.namelist()
                        self.assertEqual(len(names), len({x.casefold() for x in names}))
                        for info in archive.infolist():
                            name = PurePosixPath(info.filename)
                            self.assertFalse(name.is_absolute())
                            self.assertNotIn("..", name.parts)
                            self.assertNotIn("\\", info.filename)
                            self.assertNotIn(":", info.filename)
                            self.assertEqual((info.external_attr >> 16) & 0o170000, 0o100000)
                        prefix = "skills/content-operations/" if target == "openai" else "" if target == "gemini" else "content-operations/"
                        self.assertIn(prefix + "SKILL.md", names)
                        licence = "LICENSE.txt" if target == "gemini" else "LICENSE"
                        self.assertEqual(archive.read(prefix + licence).decode().strip().splitlines(), (ROOT / "LICENSE").read_text().strip().splitlines())
                        self.assertIn(prefix + "references/upstream-notice.md", names)
                        skill_source = (SKILL / "SKILL.md").read_bytes()
                        if target == "gemini":
                            description = skill_source.decode().split("description: >-\n  ", 1)[1].split("\n", 1)[0]
                            skill_source = skill_source.replace(("description: >-\n  " + description + "\n").encode(), ("description: " + json.dumps(description, ensure_ascii=False) + "\n").encode(), 1)
                            for template in (SKILL / "templates").glob("*.template.json"):
                                old = "templates/" + template.name
                                skill_source = skill_source.replace(old.encode(), (old + ".txt").encode())
                        self.assertEqual(archive.read(prefix + "SKILL.md"), skill_source)
                        if target == "openai":
                            manifest = json.loads(archive.read("plugin.json"))
                            self.assertEqual(manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
                            self.assertNotIn("mcp.json", names)
                        archive.extractall(extracted)  # Only the just-checked local builder output.
                    skill = extracted / prefix
                    before = {p.relative_to(extracted).as_posix(): p.read_bytes() for p in extracted.rglob("*") if p.is_file()}
                    for p in extracted.rglob("*"):
                        if p.is_file(): p.chmod(0o444)
                    try:
                        result = subprocess.run([sys.executable, "-B", str(skill / "scripts/smoke_test.py")], cwd=extracted, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertFalse(json.loads(result.stdout)["host_import_or_activation_verified"])
                        after = {p.relative_to(extracted).as_posix(): p.read_bytes() for p in extracted.rglob("*") if p.is_file()}
                        self.assertEqual(before, after)
                    finally:
                        for p in extracted.rglob("*"):
                            if p.is_file(): p.chmod(0o666)

    def test_disposable_gemini_and_shared_alias(self):
        with temporary_directory() as folder:
            home = Path(folder)
            self.assertEqual(self.command("install.py", "--host", "gemini", "--home", home, "--check").returncode, 0)
            self.assertFalse((home / ".gemini").exists())
            self.assertEqual(self.command("install.py", "--host", "gemini", "--home", home).returncode, 0)
            self.assertEqual((home / ".gemini/skills/content-operations/SKILL.md").read_bytes(), (SKILL / "SKILL.md").read_bytes())
        with temporary_directory() as folder:
            home = Path(folder)
            self.assertEqual(self.command("install.py", "--host", "all", "--home", home).returncode, 0)
            self.assertTrue((home / ".agents/skills/content-operations/SKILL.md").is_file())
            self.assertTrue((home / ".claude/skills/content-operations/SKILL.md").is_file())
            self.assertFalse((home / ".gemini").exists())
            self.assertEqual(self.command("install.py", "--host", "gemini", "--home", home).returncode, 0)
            self.assertFalse((home / ".gemini").exists())

    def test_gemini_upload_types_preserve_templates_and_notices(self):
        result = package.members(target="gemini")
        self.assertTrue(all(PurePosixPath(name).suffix in {".md", ".py", ".txt"} for name in result))
        self.assertNotIn("agents/openai.yaml", result)
        self.assertEqual(result["LICENSE.txt"], (SKILL / "LICENSE").read_bytes())
        self.assertEqual(result["references/upstream-notice.md"], (SKILL / "references/upstream-notice.md").read_bytes())
        for template in (SKILL / "templates").glob("*.template.json"):
            self.assertEqual(result["templates/" + template.name + ".txt"], template.read_bytes())
            self.assertIsInstance(json.loads(result["templates/" + template.name + ".txt"]), dict)

    def test_gemini_python_changes_only_the_packaged_template_path(self):
        result = package.members(target="gemini")
        for script in (SKILL / "scripts").glob("*.py"):
            expected = script.read_bytes()
            if script.name == "smoke_test.py":
                expected = expected.replace(b"templates/production-manifest.template.json", b"templates/production-manifest.template.json.txt")
            self.assertEqual(result["scripts/" + script.name], expected)

    def test_gemini_description_is_literal_single_line_and_preserves_meaning(self):
        frontmatter = package.members(target="gemini")["SKILL.md"].decode().split("---", 2)[1]
        description = next(line[len("description: "):] for line in frontmatter.splitlines() if line.startswith("description: "))
        original = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        self.assertEqual(json.loads(description), " ".join(line.strip() for line in original.split("description: >-\n", 1)[1].splitlines()))
        self.assertNotEqual(description, ">-")

    def test_gemini_folded_description_handles_windows_and_multiline_source(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for newline in ("\n", "\r\n"):
                with self.subTest(newline=repr(newline)):
                    content = newline.join(["---", "name: synthetic-skill", "description: >-", "  First sentence.", "  Second sentence.", "---", "# Synthetic", ""])
                    (source / "SKILL.md").write_bytes(content.encode())
                    packaged = package.members(source=source, target="gemini")["SKILL.md"]
                    self.assertIn(b'description: "First sentence. Second sentence."\n', packaged)
                    self.assertNotIn(b"description: >-", packaged)
                    self.assertTrue(packaged.endswith(("# Synthetic" + newline).encode()))
                    self.assertEqual(package.members(source=source, target="claude")["synthetic-skill/SKILL.md"], content.encode())

    def test_gemini_unknown_multiline_description_fails_explicitly(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            (source / "SKILL.md").write_text("---\nname: synthetic-skill\ndescription: |\n  Preserve this newline.\n---\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported multiline Gemini description"):
                package.members(source=source, target="gemini")

    def test_gemini_quoted_description_preserves_yaml_string_semantics(self):
        # JSON's double-quoted scalar syntax is a subset of YAML. Parse the
        # emitted scalar rather than comparing implementation formatting.
        cases = ['Review releases: preserve evidence.', 'Review release # tags.',
                 '"Review offline records"', '2026', 'true', 'null',
                 r'Review C:\synthetic\draft', 'Review caf\u00e9 \U0001f4dd',
                 'Keep trailing spaces.  ']
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for description in cases:
                with self.subTest(description=description):
                    (source / "SKILL.md").write_text("---\nname: synthetic-skill\ndescription: >-\n  " + description + "\n---\n", encoding="utf-8")
                    packaged = package.members(source=source, target="gemini")["SKILL.md"].decode()
                    scalar = next(line.removeprefix("description: ") for line in packaged.splitlines() if line.startswith("description: "))
                    self.assertEqual(json.loads(scalar), description)
                    self.assertIsInstance(json.loads(scalar), str)

    def test_gemini_complex_folded_descriptions_fail_instead_of_changing_meaning(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for body in ("  First\n\n  Second\n", "  First\n    Indented\n", "  \n", "  First\n\tSecond\n"):
                with self.subTest(body=body):
                    (source / "SKILL.md").write_text("---\nname: synthetic-skill\ndescription: >-\n" + body + "---\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Unsupported folded Gemini description"):
                        package.members(source=source, target="gemini")

    def test_gemini_separator_literals_preserve_description_and_body(self):
        cases = [
            ["First sentence.", "Review --- offline cases."],
            ['First "quoted" sentence.', 'Review --- releases: keep # tags and "quotes".'],
            ["First sentence.", "---", "Last sentence."],
            ["---", "----", "--- trailing text", "..."],
            ["Review caf\u00e9 --- offline.", r"Keep C:\synthetic\draft --- unchanged."],
        ]
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for newline in ("\n", "\r\n"):
                for lines in cases:
                    with self.subTest(newline=repr(newline), lines=lines):
                        prefix = newline.join(["---", "name: synthetic-skill", ""])
                        folded = "description: >-" + newline + "".join("  " + line + newline for line in lines)
                        # The body deliberately repeats the exact metadata text.
                        # Only the bounded header may be converted.
                        suffix = newline.join(["compatibility: offline", "---", "# Synthetic --- body", ""]) + folded + "---" + newline
                        content = (prefix + folded + suffix).encode("utf-8")
                        (source / "SKILL.md").write_bytes(content)
                        packaged = package.members(source=source, target="gemini")["SKILL.md"]
                        scalar = json.dumps(" ".join(lines), ensure_ascii=False)
                        expected = (prefix + "description: " + scalar + "\n" + suffix).encode("utf-8")
                        self.assertEqual(packaged, expected)
                        emitted = next(line.removeprefix("description: ") for line in packaged.decode("utf-8").splitlines() if line.startswith("description: "))
                        self.assertEqual(json.loads(emitted), " ".join(lines))
                        self.assertEqual((source / "SKILL.md").read_bytes(), content)
                        self.assertEqual(package.members(source=source, target="claude")["synthetic-skill/SKILL.md"], content)

    def test_frontmatter_boundary_lines_preserve_spacing_and_end_of_file(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for newline in ("\n", "\r\n"):
                for padding in ("", " ", "\t"):
                    for final_newline in ("", newline):
                        with self.subTest(newline=repr(newline), padding=repr(padding), final=repr(final_newline)):
                            content = ("---" + padding + newline + "name: synthetic-skill" + newline
                                       + 'description: "Keep --- inside quotes"' + newline + "---" + padding + final_newline).encode()
                            (source / "SKILL.md").write_bytes(content)
                            self.assertEqual(package.members(source=source, target="gemini")["SKILL.md"], content)

    def test_frontmatter_names_and_inline_quotes_do_not_consume_body_markers(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for newline in ("\n", "\r\n"):
                content = newline.join(["---", 'description: "Review --- and \\"quotes\\""',
                                        "name: synthetic-skill", "---", "# Body", "---",
                                        "name: wrong-skill", "---", ""]).encode()
                (source / "SKILL.md").write_bytes(content)
                self.assertEqual(package.members(source=source, target="gemini")["SKILL.md"], content)

    def test_malformed_or_missing_frontmatter_boundaries_fail_closed(self):
        header = "name: synthetic-skill\ndescription: test\n"
        cases = [
            header + "---\n", "---\n" + header,
            "preamble\n---\n" + header + "---\n",
            "\ufeff---\n" + header + "---\n",
            "---\r" + header + "---\n",
            "---\n" + header + "---\r",
            "---\nname: synthetic-skill\rdescription: test\n---\n",
            "---\n---\n" + header + "---\n",
            "---\nname: wrong-skill\ndescription: test\n---\n" + header,
        ]
        for marker in ("----", "---not-a-boundary", "--- # comment", "  ---", "prefix---"):
            cases.extend([marker + "\n" + header + "---\n", "---\n" + header + marker + "\n"])
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for content in cases:
                for target in ("claude", "codex", "gemini", "openai"):
                    with self.subTest(content=repr(content), target=target):
                        (source / "SKILL.md").write_bytes(content.encode("utf-8"))
                        with self.assertRaises(ValueError):
                            package.members(source=source, target=target)

    def test_unsupported_folds_with_separator_literals_fail_explicitly(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            for newline in ("\n", "\r\n"):
                for lines in (["  First --- sentence.", "", "  Last sentence."],
                              ["  First sentence.", "    ---"],
                              ["  First --- sentence.", "\tLast sentence."]):
                    with self.subTest(newline=repr(newline), lines=lines):
                        content = newline.join(["---", "name: synthetic-skill", "description: >-", *lines, "---", ""])
                        (source / "SKILL.md").write_bytes(content.encode())
                        with self.assertRaisesRegex(ValueError, "Unsupported folded Gemini description"):
                            package.members(source=source, target="gemini")

    def test_legacy_discovery_blocks_before_any_copy(self):
        with temporary_directory() as folder:
            home = Path(folder)
            old = home / ".codex/skills/content-operations"
            old.mkdir(parents=True)
            (old / "SKILL.md").write_text("preserve existing installation")
            self.assertNotEqual(self.command("install.py", "--host", "all", "--home", home).returncode, 0)
            self.assertFalse((home / ".agents").exists())
            self.assertFalse((home / ".claude").exists())

    def test_differing_gemini_alias_blocks_shared_copy(self):
        with temporary_directory() as folder:
            home = Path(folder)
            old = home / ".gemini/skills/content-operations"
            old.mkdir(parents=True)
            (old / "SKILL.md").write_text("preserve differing Gemini copy")
            self.assertNotEqual(self.command("install.py", "--host", "all", "--home", home).returncode, 0)
            self.assertFalse((home / ".agents").exists())
            self.assertFalse((home / ".claude").exists())
            self.assertEqual((old / "SKILL.md").read_text(), "preserve differing Gemini copy")

    def test_unrecognised_private_record_is_not_packaged(self):
        with temporary_directory() as folder:
            source = Path(folder) / "test-skill"
            source.mkdir()
            (source / "SKILL.md").write_text("---\nname: test-skill\ndescription: test\n---\n")
            (source / "tracker.json").write_text('{"synthetic": true}')
            with self.assertRaises(ValueError): package.members(source)

    def test_missing_runtime_is_failure_not_claimed_execution(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["smoke_test.py"]), patch.object(sys, "version_info", (3, 9)), contextlib.redirect_stdout(output):
            self.assertEqual(smoke.main(), 1)
        self.assertFalse(json.loads(output.getvalue())["passed"])


if __name__ == "__main__":
    unittest.main()
