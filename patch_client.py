#!/usr/bin/env python3
"""Version-locked grant-all patcher for VoiceMeeter Potato 3.1.2.2.

The patch preserves the normal activation-success block but bypasses the local
certificate verifier after non-empty email and response values are loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DIRECTORY = Path(r"C:\Program Files (x86)\VB\Voicemeeter")
BACKUP_SUFFIX = ".aero-original"


@dataclass(frozen=True)
class Target:
    name: str
    filename: str
    original_sha256: str
    patch_rva: int
    expected: bytes
    replacement: bytes


TARGETS = {
    "x86": Target(
        name="32-bit",
        filename="voicemeeter8.exe",
        original_sha256="E1F2CDF2990FDF3D96057E18FE441E81F91385B5F63F87A6432B8B3708B92520",
        patch_rva=0x260A0,
        expected=bytes.fromhex("538bcfe8a8f9ffffb901"),
        replacement=bytes.fromhex("b901000000e918000000"),
    ),
    "x64": Target(
        name="64-bit",
        filename="voicemeeter8x64.exe",
        original_sha256="738C876013EAA7EF09C42C4F156B68FBE98A8EB702160EC920D855CE2E8FB2BD",
        patch_rva=0x21BF3,
        expected=bytes.fromhex("488b542440488bcbe8b0"),
        replacement=bytes.fromhex("b801000000e911000000"),
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rva_to_offset(data: bytes, rva: int) -> int:
    if data[:2] != b"MZ":
        raise ValueError("not a PE file")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("invalid PE signature")
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    table = pe_offset + 24 + optional_size
    for index in range(section_count):
        section = table + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, section + 8
        )
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            delta = rva - virtual_address
            if delta >= raw_size:
                raise ValueError("patch RVA has no file-backed data")
            return raw_pointer + delta
    raise ValueError(f"RVA 0x{rva:X} is outside all sections")


def inspect(data: bytes, target: Target) -> tuple[str, int]:
    offset = rva_to_offset(data, target.patch_rva)
    if digest(data) == target.original_sha256:
        if data[offset : offset + len(target.expected)] != target.expected:
            raise ValueError("original hash matched but expected patch bytes did not")
        return "original", offset

    if data[offset : offset + len(target.replacement)] == target.replacement:
        restored = bytearray(data)
        restored[offset : offset + len(target.expected)] = target.expected
        if digest(restored) == target.original_sha256:
            return "patched", offset
    return "unknown", offset


def selected_targets(selection: str):
    return TARGETS.values() if selection == "all" else [TARGETS[selection]]


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def replace_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".aero-tmp")
    try:
        shutil.copy2(path, temporary)
        with temporary.open("r+b") as stream:
            stream.seek(0)
            stream.write(data)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def status(directory: Path, targets) -> int:
    result = 0
    for target in targets:
        path = directory / target.filename
        try:
            state, offset = inspect(path.read_bytes(), target)
            print(f"{target.name}: {state}; {path}; patch file offset 0x{offset:X}")
            result |= state == "unknown"
        except (OSError, ValueError) as exc:
            print(f"{target.name}: ERROR: {exc}", file=sys.stderr)
            result = 1
    return int(result)


def apply(directory: Path, targets, dry_run: bool) -> int:
    plans = []
    for target in targets:
        path = directory / target.filename
        try:
            data = path.read_bytes()
            state, offset = inspect(data, target)
            if state == "patched":
                print(f"{target.name}: already patched")
                continue
            if state != "original":
                raise ValueError("unsupported or modified binary; refusing to patch")
            plans.append((target, path, data, offset))
        except (OSError, ValueError) as exc:
            print(f"{target.name}: ERROR: {exc}", file=sys.stderr)
            return 1

    for target, path, data, offset in plans:
        backup = backup_path(path)
        if backup.exists() and digest(backup.read_bytes()) != target.original_sha256:
            print(f"{target.name}: ERROR: invalid backup at {backup}", file=sys.stderr)
            return 1
        if dry_run:
            print(f"{target.name}: would back up and patch {path}")
            continue
        if not backup.exists():
            shutil.copy2(path, backup)
        patched = bytearray(data)
        patched[offset : offset + len(target.replacement)] = target.replacement
        replace_bytes(path, patched)
        state, _ = inspect(path.read_bytes(), target)
        if state != "patched":
            raise RuntimeError(f"post-write verification failed for {path}")
        print(f"{target.name}: patched; backup={backup}")
    return 0


def restore(directory: Path, targets, dry_run: bool) -> int:
    for target in targets:
        path = directory / target.filename
        backup = backup_path(path)
        try:
            original = backup.read_bytes()
            if digest(original) != target.original_sha256:
                raise ValueError("backup does not match the supported original")
            if dry_run:
                print(f"{target.name}: would restore {path} from {backup}")
                continue
            replace_bytes(path, original)
            state, _ = inspect(path.read_bytes(), target)
            if state != "original":
                raise RuntimeError("post-restore verification failed")
            print(f"{target.name}: restored from {backup}")
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{target.name}: ERROR: {exc}", file=sys.stderr)
            return 1
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "apply", "restore"))
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--target", choices=("all", "x86", "x64"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    targets = list(selected_targets(args.target))
    try:
        if args.action == "status":
            return status(args.directory, targets)
        if args.action == "apply":
            return apply(args.directory, targets, args.dry_run)
        return restore(args.directory, targets, args.dry_run)
    except (OSError, PermissionError, RuntimeError) as exc:
        print(
            f"ERROR: {exc}\nClose VoiceMeeter and run from an elevated shell if "
            "the installation directory is protected.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
