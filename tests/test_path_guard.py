"""Synthetic files and supplied stat metadata only; never create OS links."""
import json
import contextlib
import io
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_checks import module, temporary_directory, ROOT, SKILL
from test_portability import package, root_module

guard = module("path_guard")
installer = root_module("install")
adapter = module("adapt_tracker")


def metadata(mode=stat.S_IFREG | 0o644, links=1, attributes=0, tag=0):
    return SimpleNamespace(st_mode=mode, st_nlink=links, st_file_attributes=attributes, st_reparse_tag=tag)


class PathGuardTests(unittest.TestCase):
    def test_metadata_detects_hardlinks_symlinks_and_pre312_reparse_points(self):
        for info in (metadata(links=2), metadata(mode=stat.S_IFLNK | 0o777),
                     metadata(mode=stat.S_IFDIR, attributes=0x400), metadata(mode=stat.S_IFDIR, tag=0xa0000003)):
            self.assertTrue(guard.linked_metadata(info))
            fake_path = SimpleNamespace(lstat=lambda: info)  # No is_junction method.
            self.assertTrue(package.linked(fake_path))
        self.assertFalse(guard.linked_metadata(metadata()))
        self.assertFalse(guard.linked_metadata(metadata(mode=stat.S_IFDIR, links=7)))
        # Match independent probes; no actual hardlink/junction operation is attempted.
        self.assertTrue(package.linked(SimpleNamespace(stat=lambda: SimpleNamespace(st_nlink=2))))
        self.assertTrue(package.linked(SimpleNamespace(lstat=lambda: SimpleNamespace(st_file_attributes=0x400, st_reparse_tag=0xa0000003))))

    def test_unsafe_names_refused_before_stat_or_open(self):
        names = ["file.json:stream", "file.json::$DATA", "dir:stream/file.zip", "NUL", "con.txt", "COM1.log", "lpt³", "CONOUT$",
                 "safe/NUL .txt", "file. ", "file.", "../file", "C:relative.zip", r"C:\safe\file:stream",
                 r"\\?\C:\safe\file.zip", r"\\.\GLOBALROOT\Device\file", r"\\server\share\file.zip", "//server/share/file.zip", "bad\nname"]
        for name in names:
            with self.subTest(name=name), patch.object(Path, "lstat", side_effect=AssertionError("No filesystem query allowed")):
                with self.assertRaises(guard.UnsafePath): guard.checked_path(name, new_file=True)

    def test_plain_local_names_remain_supported(self):
        for name in ("review.json", "space café/result.zip", r"C:\safe\review.json", "/tmp/review.json"):
            guard.validate_path_text(name)
        with temporary_directory() as folder:
            self.assertEqual(guard.checked_path(Path(folder) / "new.json", new_file=True), Path(folder) / "new.json")

    def test_adapter_source_stream_refused_before_resolution_or_read(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["adapt_tracker.py", "synthetic.json:stream", "--namespace", "test"]), \
                patch.object(Path, "resolve", side_effect=AssertionError("Must not resolve stream input")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("Must not read stream input")), contextlib.redirect_stdout(output):
            self.assertEqual(adapter.main(), 1)
        self.assertIn("Streams", json.loads(output.getvalue())["error"])

    def test_source_tree_and_install_hashes_reject_supplied_hardlink_metadata(self):
        with temporary_directory() as folder:
            source = Path(folder) / "synthetic-skill"
            source.mkdir()
            linked_file = source / "SKILL.md"
            linked_file.write_text("---\nname: synthetic-skill\ndescription: synthetic\n---\n")
            original_lstat = Path.lstat
            def simulated(path, *args, **kwargs):
                return metadata(links=2) if path == linked_file else original_lstat(path, *args, **kwargs)
            with patch.object(Path, "lstat", simulated):
                with self.assertRaises(guard.UnsafePath): guard.source_files(source)
                with self.assertRaises(package.path_guard.UnsafePath): package.members(source)
                with self.assertRaises(installer.path_guard.UnsafePath): installer.hashes(source)

    def test_output_parents_reject_pre312_junction_metadata(self):
        with temporary_directory() as folder:
            parent = Path(folder)
            original_lstat = Path.lstat
            def simulated(path, *args, **kwargs):
                return metadata(mode=stat.S_IFDIR, attributes=0x400, tag=0xa0000003) if path == parent else original_lstat(path, *args, **kwargs)
            with patch.object(Path, "lstat", simulated):
                with self.assertRaises(guard.UnsafePath): guard.checked_path(parent / "new.json", new_file=True)

    def test_source_tree_reparse_parent_refused_before_traversal(self):
        with temporary_directory() as folder:
            root = Path(folder)
            original_lstat = Path.lstat
            def simulated(path, *args, **kwargs):
                return metadata(mode=stat.S_IFDIR, attributes=0x400) if path == root else original_lstat(path, *args, **kwargs)
            with patch.object(Path, "lstat", simulated), patch.object(Path, "iterdir", side_effect=AssertionError("Traversal must not start")):
                with self.assertRaises(guard.UnsafePath): guard.source_files(root)

    def test_adapter_and_packager_refuse_stream_without_creating_it(self):
        with temporary_directory() as folder:
            root = Path(folder)
            src = root / "synthetic.json"
            data = b'{"schema_version":1,"scheduled":[{"id":1,"platform":"instagram","scheduler":"Metricool"}]}'
            src.write_bytes(data)
            for suffix in (":snapshot", "::$DATA"):
                output = str(src) + suffix
                before = set(root.iterdir())
                adapter_run = subprocess.run([sys.executable, "-B", str(SKILL / "scripts/adapt_tracker.py"), str(src), "--namespace", "synthetic", "--out", output], capture_output=True, text=True)
                self.assertEqual(adapter_run.returncode, 1, adapter_run.stdout)
                self.assertFalse(json.loads(adapter_run.stdout)["ingested"])
                package_run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/package.py"), "--out", output], capture_output=True, text=True)
                self.assertNotEqual(package_run.returncode, 0, package_run.stdout)
                self.assertEqual(src.read_bytes(), data)
                self.assertEqual(before, set(root.iterdir()))
                if suffix == ":snapshot": self.assertFalse(Path(output).exists())


if __name__ == "__main__":
    unittest.main()
