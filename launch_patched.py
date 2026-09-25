#!/usr/bin/env python3
"""Launch an original VoiceMeeter 3.1.2.2 image with the grant patch in memory."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import subprocess
import sys
from pathlib import Path

from patch_client import DEFAULT_DIRECTORY, TARGETS, inspect


CREATE_SUSPENDED = 0x00000004
PAGE_EXECUTE_READWRITE = 0x40
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
ERROR_BAD_LENGTH = 24
ERROR_PARTIAL_COPY = 299
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(wintypes.BYTE)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.BOOL,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW),
    ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32FirstW.restype = wintypes.BOOL
kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32NextW.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.VirtualProtectEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.VirtualProtectEx.restype = wintypes.BOOL
kernel32.FlushInstructionCache.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    ctypes.c_size_t,
]
kernel32.FlushInstructionCache.restype = wintypes.BOOL
kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
kernel32.ResumeThread.restype = wintypes.DWORD
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
ntdll.NtQueryInformationProcess.argtypes = [
    wintypes.HANDLE,
    wintypes.ULONG,
    wintypes.LPVOID,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
ntdll.NtQueryInformationProcess.restype = wintypes.LONG


def winerror(message: str) -> OSError:
    error = ctypes.get_last_error()
    return OSError(error, f"{message}: {ctypes.FormatError(error)}")


def read_remote(process_handle, address: int, size: int) -> bytes:
    buffer = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        process_handle,
        ctypes.c_void_p(address),
        buffer,
        size,
        ctypes.byref(read),
    ):
        raise winerror("ReadProcessMemory failed")
    if read.value != size:
        raise RuntimeError("ReadProcessMemory performed a short read")
    return bytes(buffer)


def peb_image_base(process_handle, architecture: str) -> int:
    if architecture == "x86" and ctypes.sizeof(ctypes.c_void_p) == 8:
        wow64_peb = ctypes.c_void_p()
        status = ntdll.NtQueryInformationProcess(
            process_handle,
            26,  # ProcessWow64Information
            ctypes.byref(wow64_peb),
            ctypes.sizeof(wow64_peb),
            None,
        )
        if status == 0 and wow64_peb.value:
            return int.from_bytes(
                read_remote(process_handle, wow64_peb.value + 0x8, 4), "little"
            )

    basic = PROCESS_BASIC_INFORMATION()
    status = ntdll.NtQueryInformationProcess(
        process_handle,
        0,  # ProcessBasicInformation
        ctypes.byref(basic),
        ctypes.sizeof(basic),
        None,
    )
    if status != 0 or not basic.PebBaseAddress:
        raise RuntimeError(f"NtQueryInformationProcess failed: NTSTATUS 0x{status & 0xFFFFFFFF:08X}")
    pointer_size = 8 if architecture == "x64" else 4
    image_offset = 0x10 if pointer_size == 8 else 0x8
    return int.from_bytes(
        read_remote(process_handle, basic.PebBaseAddress + image_offset, pointer_size),
        "little",
    )


def module_base(process_handle, process_id: int, filename: str, architecture: str) -> int:
    try:
        base = peb_image_base(process_handle, architecture)
        if base:
            return base
    except (OSError, RuntimeError):
        pass

    snapshot = INVALID_HANDLE_VALUE
    last_error = 0
    # A 64-bit enumerator targeting WOW64 can reject the combined module flags
    # with ERROR_PARTIAL_COPY. Retry with the explicit 32-bit view.
    for flags in (
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
        TH32CS_SNAPMODULE32,
        TH32CS_SNAPMODULE,
    ):
        ctypes.set_last_error(0)
        snapshot = kernel32.CreateToolhelp32Snapshot(flags, process_id)
        if snapshot != INVALID_HANDLE_VALUE:
            break
        last_error = ctypes.get_last_error()
        if last_error not in (ERROR_BAD_LENGTH, ERROR_PARTIAL_COPY):
            break
    if snapshot == INVALID_HANDLE_VALUE:
        ctypes.set_last_error(last_error)
        raise winerror("CreateToolhelp32Snapshot failed")
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Module32FirstW(snapshot, ctypes.byref(entry)):
            raise winerror("Module32FirstW failed")
        while True:
            if entry.szModule.casefold() == filename.casefold():
                return ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
            if not kernel32.Module32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    raise RuntimeError(f"could not find {filename} in suspended process")


def launch(directory: Path, architecture: str, extra_args: list[str]) -> int:
    target = TARGETS[architecture]
    executable = (directory / target.filename).resolve()
    data = executable.read_bytes()
    state, _ = inspect(data, target)
    if state != "original":
        raise RuntimeError(
            f"{executable} is {state}; restore the signed original before launch"
        )

    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    process = PROCESS_INFORMATION()
    arguments = [str(executable), *extra_args]
    command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))

    if not kernel32.CreateProcessW(
        str(executable),
        command_line,
        None,
        None,
        False,
        CREATE_SUSPENDED,
        None,
        str(directory.resolve()),
        ctypes.byref(startup),
        ctypes.byref(process),
    ):
        raise winerror("CreateProcessW failed")

    resumed = False
    try:
        base = module_base(
            process.hProcess, process.dwProcessId, target.filename, architecture
        )
        address = base + target.patch_rva
        current = (ctypes.c_ubyte * len(target.expected))()
        read = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            process.hProcess,
            ctypes.c_void_p(address),
            current,
            len(current),
            ctypes.byref(read),
        ):
            raise winerror("ReadProcessMemory failed")
        if bytes(current) != target.expected:
            raise RuntimeError(
                f"runtime bytes at 0x{address:X} do not match the supported build"
            )

        old_protection = wintypes.DWORD()
        if not kernel32.VirtualProtectEx(
            process.hProcess,
            ctypes.c_void_p(address),
            len(target.replacement),
            PAGE_EXECUTE_READWRITE,
            ctypes.byref(old_protection),
        ):
            raise winerror("VirtualProtectEx failed")
        try:
            replacement = (ctypes.c_ubyte * len(target.replacement)).from_buffer_copy(
                target.replacement
            )
            written = ctypes.c_size_t()
            if not kernel32.WriteProcessMemory(
                process.hProcess,
                ctypes.c_void_p(address),
                replacement,
                len(replacement),
                ctypes.byref(written),
            ):
                raise winerror("WriteProcessMemory failed")
            if written.value != len(target.replacement):
                raise RuntimeError("WriteProcessMemory performed a short write")
            if not kernel32.FlushInstructionCache(
                process.hProcess, ctypes.c_void_p(address), len(target.replacement)
            ):
                raise winerror("FlushInstructionCache failed")
        finally:
            ignored = wintypes.DWORD()
            kernel32.VirtualProtectEx(
                process.hProcess,
                ctypes.c_void_p(address),
                len(target.replacement),
                old_protection.value,
                ctypes.byref(ignored),
            )

        if kernel32.ResumeThread(process.hThread) == 0xFFFFFFFF:
            raise winerror("ResumeThread failed")
        resumed = True
        print(
            f"launched {target.name} VoiceMeeter PID={process.dwProcessId}; "
            f"in-memory patch address=0x{address:X}"
        )
        return 0
    finally:
        if not resumed:
            kernel32.TerminateProcess(process.hProcess, 1)
        kernel32.CloseHandle(process.hThread)
        kernel32.CloseHandle(process.hProcess)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--target", choices=("x86", "x64"), default="x86")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments for VoiceMeeter")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    if sys.platform != "win32":
        print("ERROR: this launcher requires Windows", file=sys.stderr)
        return 1
    args = parse_args(argv)
    target = TARGETS[args.target]
    path = args.directory / target.filename
    try:
        state, offset = inspect(path.read_bytes(), target)
        if state != "original":
            raise RuntimeError(f"binary state is {state}; expected original")
        if args.dry_run:
            print(
                f"OK: {target.name} original verified; file offset=0x{offset:X}; "
                "no process started"
            )
            return 0
        extra = args.args[1:] if args.args[:1] == ["--"] else args.args
        return launch(args.directory, args.target, extra)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
