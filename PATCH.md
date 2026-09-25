# Grant-all patch details

The patch is deliberately locked to the two VoiceMeeter Potato 3.1.2.2
executables inspected in this lab.

| Binary | Original SHA-256 | Patch RVA | File offset |
|---|---|---:|---:|
| `voicemeeter8.exe` | `E1F2CDF2990FDF3D96057E18FE441E81F91385B5F63F87A6432B8B3708B92520` | `0x260A0` | `0x254A0` |
| `voicemeeter8x64.exe` | `738C876013EAA7EF09C42C4F156B68FBE98A8EB702160EC920D855CE2E8FB2BD` | `0x21BF3` | `0x20FF3` |

## Control-flow change

Both activation evaluators first load and normalize the registry `email` and
`serial` values. If either value is empty, the original failure path is still
taken. With both values present, the original code invokes the certificate
verifier and compares a certificate-derived value with the current challenge.

The patch replaces that verifier-and-compare entry with:

```text
x86:  mov ecx, 1
      jmp existing_success_block

x64:  mov eax, 1
      jmp existing_success_block
```

The existing success block sets the activated/cache fields, updates the caller's
state, and returns success. No parser or cryptographic primitive is modified.

## Exact byte changes

```text
x86 at RVA 0x260A0
before: 53 8B CF E8 A8 F9 FF FF B9 01
after:  B9 01 00 00 00 E9 18 00 00 00

x64 at RVA 0x21BF3
before: 48 8B 54 24 40 48 8B CB E8 B0
after:  B8 01 00 00 00 E9 11 00 00 00
```

`patch_client.py` verifies the complete original SHA-256 and expected bytes
before writing. Status detection for patched files substitutes the original
bytes in memory and requires the reconstructed file to match the original
SHA-256. Restore accepts only a hash-matching `.aero-original` backup.

`launch_patched.py` is the recommended execution method. It requires the
original hash-matching executable, creates it suspended, verifies the runtime
bytes after ASLR relocation, temporarily makes the target page writable,
writes the same replacement bytes, flushes the instruction cache, restores the
page protection, and resumes the initial thread. The signed file on disk is
never changed and the patch vanishes when the process exits.
