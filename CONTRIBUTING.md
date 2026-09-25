# Contributing

Contributions should preserve the repository's narrow scope: reproducible
analysis and isolated testing of the VoiceMeeter activation protocol.

## Before opening a pull request

1. Create a focused branch.
2. Keep runtime code dependency-free unless a dependency is technically
   necessary and justified in the pull request.
3. Run:

   ```powershell
   python -m compileall -q .
   python -m unittest -v test_emulator.py
   ```

4. Parse both PowerShell scripts or run the repository CI workflow.
5. Update documentation when behavior, protocol assumptions, offsets, or
   supported hashes change.

## Version-specific changes

Support for another client build must include:

- Exact file version and SHA-256 for every supported architecture.
- Verified RVAs and expected original bytes.
- Disassembly or equivalent reasoning showing the control-flow target.
- A clean refusal path for unknown binaries.
- Restore or non-persistent execution behavior.
- Tests that do not redistribute proprietary binaries.

Never weaken the full-file hash and expected-byte checks merely to make another
build appear compatible.

## Data that must not be committed

- VoiceMeeter or VB-Audio binaries.
- Customer email addresses, response codes, or certificates.
- Raw captured `cmd` envelopes.
- Generated TLS private keys or certificates.
- `.aero-original` backups.
- Registry exports or logs containing personal machine identifiers.

Use synthetic fixtures and redact diagnostic output before attaching it to an
issue or pull request.
