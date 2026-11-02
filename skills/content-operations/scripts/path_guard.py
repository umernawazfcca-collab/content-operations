"""Conservative portable path preflight, not a concurrent filesystem sandbox.

Uses lstat/reparse/link-count metadata available before Python 3.12. Never creates
links or changes permissions. Callers must retain exclusive output creation and
use a stable directory controlled by the operator (no concurrent path swapping).
"""
import os
import re
import stat
from pathlib import Path, PureWindowsPath


class UnsafePath(ValueError):
    pass


def validate_path_text(value):
    """Refuse Windows streams/devices on every host before any filesystem access."""
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw or any(ord(c) < 32 for c in raw):
        raise UnsafePath("Path must be ordinary text without control characters")
    if raw.replace("\\", "/").startswith("//"):
        raise UnsafePath("Network and device namespaces are unsupported")
    windows = PureWindowsPath(raw)
    if windows.drive and (not re.fullmatch(r"[A-Za-z]:", windows.drive) or not windows.root):
        raise UnsafePath("Drive-relative and device paths are unsupported")
    parts = windows.parts[1:] if windows.anchor else windows.parts
    reserved = re.compile(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])", re.I)
    for part in parts:
        if part in (".", "..") or part.endswith((".", " ")) or any(c in part for c in ':<>"|?*'):
            raise UnsafePath("Streams, dot segments and reserved filename syntax are unsupported")
        if reserved.fullmatch(part.split(".", 1)[0].rstrip(" .")):
            raise UnsafePath("Reserved device names are unsupported")


def linked_metadata(info):
    """Interpret no-follow metadata; directory link counts are not file hardlinks."""
    if getattr(info, "st_file_attributes", 0) & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        return True
    if getattr(info, "st_reparse_tag", 0):
        return True
    mode = getattr(info, "st_mode", 0)
    if stat.S_ISLNK(mode):
        return True
    return not stat.S_ISDIR(mode) and getattr(info, "st_nlink", 1) > 1


def linked(path):
    try:
        # pathlib.Path always supplies lstat on supported runtimes. The fallback
        # supports simple supplied-stat test objects, never follows a real Path.
        info = path.lstat() if hasattr(path, "lstat") else path.stat()
    except FileNotFoundError:
        return False
    return linked_metadata(info)


def checked_path(value, *, new_file=False):
    """Validate a local path and every existing parent without resolving links."""
    validate_path_text(value)
    if os.name != "nt" and PureWindowsPath(os.fspath(value)).drive:
        raise UnsafePath("Windows drive paths require a Windows host")
    path = Path(value).absolute()
    validate_path_text(path)
    for index, candidate in enumerate((path, *path.parents)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if linked_metadata(info):
            raise UnsafePath("Linked files, reparse points and linked parents are unsupported")
        if index == 0:
            if new_file:
                raise UnsafePath("Output must be a new ordinary file")
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise UnsafePath("Only ordinary files and directories are supported")
        elif not stat.S_ISDIR(info.st_mode):
            raise UnsafePath("An existing parent is not an ordinary directory")
    return path


def source_files(root):
    """Walk only inspected ordinary directories; reject links before descending."""
    root = checked_path(root)
    if not root.is_dir():
        raise UnsafePath("Source must be an existing ordinary directory")
    pending = [root]
    files = []
    while pending:
        folder = pending.pop()
        for child in sorted(folder.iterdir()):
            validate_path_text(child)
            info = child.lstat()
            if linked_metadata(info):
                raise UnsafePath("Linked source files and reparse directories are unsupported")
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
            elif stat.S_ISREG(info.st_mode):
                files.append(child)
            else:
                raise UnsafePath("Source contains a non-regular file")
    return sorted(files)
