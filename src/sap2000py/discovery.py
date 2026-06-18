"""SAP2000 installation discovery."""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Installation:
    """One discovered SAP2000 executable."""

    version: str | None
    major: int | None
    path: Path


def _major(version: str) -> int:
    match = re.search(r"\d+", version)
    if match is None:
        raise ValueError(f"cannot parse SAP2000 major version from {version!r}.")
    return int(match.group(0))


def _version_key(version: str | None) -> tuple[int, ...] | None:
    if version is None:
        return None
    parts = [int(part) for part in re.findall(r"\d+", version)]
    return tuple(parts) if parts else None


class _VsFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD),
        ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD),
        ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD),
        ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD),
        ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD),
        ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD),
        ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


def _format_version(ms: int, ls: int) -> str | None:
    parts = [ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return ".".join(str(part) for part in parts) if any(parts) else None


def _file_version(path: Path) -> str | None:
    """Read version metadata from an executable, never from its path text."""
    if os.name != "nt" or not path.exists():
        return None
    version_dll: Any = ctypes.WinDLL("version")
    handle = wintypes.DWORD()
    size = version_dll.GetFileVersionInfoSizeW(str(path), ctypes.byref(handle))
    if not size:
        return None

    buffer = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None

    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    ok = version_dll.VerQueryValueW(
        buffer,
        "\\",
        ctypes.byref(pointer),
        ctypes.byref(length),
    )
    if not ok or length.value < ctypes.sizeof(_VsFixedFileInfo):
        return None

    info = ctypes.cast(pointer, ctypes.POINTER(_VsFixedFileInfo)).contents
    return _format_version(int(info.dwFileVersionMS), int(info.dwFileVersionLS))


def _installation(path: Path, *, version: str | None = None) -> Installation:
    resolved_version = version or _file_version(path)
    major = _major(resolved_version) if resolved_version is not None else None
    return Installation(version=resolved_version, major=major, path=path)


def _discover(candidates: list[Installation] | tuple[Installation, ...]) -> list[Installation]:
    """Deduplicate by executable path and sort known full versions first."""
    best_by_path: dict[Path, Installation] = {}
    for candidate in candidates:
        path = candidate.path
        existing = best_by_path.get(path)
        if existing is None:
            best_by_path[path] = candidate
            continue
        existing_key = _version_key(existing.version)
        candidate_key = _version_key(candidate.version)
        if existing_key is None or (candidate_key is not None and candidate_key > existing_key):
            best_by_path[path] = candidate

    def sort_key(item: Installation) -> tuple[int, tuple[int, ...], str]:
        key = _version_key(item.version)
        return (0 if key is not None else 1, tuple(-part for part in (key or ())), str(item.path))

    return sorted(best_by_path.values(), key=sort_key)


_REGISTRY_PATH_VALUE_NAMES = frozenset(
    {
        "applicationpath",
        "executable",
        "exepath",
        "installdir",
        "installpath",
        "location",
        "path",
        "program",
        "programfolder",
    }
)
_REGISTRY_VERSION_VALUE_NAMES = frozenset(
    {"displayversion", "fileversion", "productversion", "version"}
)


def _exe_from_registry_value(value: str) -> Path | None:
    path = Path(value)
    if path.name.lower() == "sap2000.exe":
        return path
    candidate = path / "SAP2000.exe"
    return candidate if candidate.exists() else None


def _registry_installations() -> list[Installation]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:  # pragma: no cover - Windows-only module
        return []

    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Computers and Structures"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Computers and Structures"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Computers and Structures"),
    ]
    candidates: list[Installation] = []

    def scan_key(root: int, subkey: str, depth: int = 0) -> None:
        if depth > 4:
            return
        try:
            with winreg.OpenKey(root, subkey) as key:
                explicit_version: str | None = None
                values: list[tuple[str, str]] = []
                index = 0
                while True:
                    try:
                        name, value, _value_type = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    index += 1
                    if isinstance(value, str):
                        values.append((name.lower(), value))
                        if name.lower().replace(" ", "") in _REGISTRY_VERSION_VALUE_NAMES:
                            explicit_version = value

                for name, value in values:
                    normalized = name.replace(" ", "")
                    if normalized not in _REGISTRY_PATH_VALUE_NAMES:
                        continue
                    exe = _exe_from_registry_value(value)
                    if exe is not None:
                        candidates.append(_installation(exe, version=explicit_version))

                index = 0
                while True:
                    try:
                        child = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    scan_key(root, rf"{subkey}\{child}", depth + 1)
        except OSError:
            return

    for root, subkey in roots:
        scan_key(root, subkey)
    return candidates


def _candidate_installations() -> list[Installation]:
    """Find candidate SAP2000.exe paths without guessing versions from path names."""
    if os.name != "nt":
        return []
    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
    ]
    candidates: list[Installation] = []
    for root in roots:
        if not root:
            continue
        base = Path(root) / "Computers and Structures"
        for exe in base.glob("SAP2000 */SAP2000.exe"):
            candidates.append(_installation(exe))
    candidates.extend(_registry_installations())
    return candidates


def installations() -> list[Installation]:
    """Return discovered SAP2000 installations."""
    return _discover(tuple(_candidate_installations()))
