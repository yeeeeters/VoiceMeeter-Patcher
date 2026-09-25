# VoiceMeeter 3.1.2.2 License Protocol Lab

Windows research tooling for the VoiceMeeter Potato 3.1.2.2 activation
protocol. The repository contains a local HTTPS endpoint emulator, a
version-locked in-memory client launcher, reversible lab-routing scripts, tests,
and reverse-engineering notes.

> [!IMPORTANT]
> This project is version-specific and intended for isolated interoperability
> and reverse-engineering research. It does not contain VoiceMeeter binaries,
> vendor private keys, or vendor-signed certificates.

## Features

- Emulates `GET /en/module/vblicensing/certify?cmd=...` over HTTP or HTTPS.
- Supports `error`, `grant`, fixed-response, and SHA-256 replay modes.
- Logs only request length and SHA-256, not the encrypted command value.
- Launches the original signed executable suspended and applies the grant patch
  only to process memory.
- Supports the inspected 32-bit and 64-bit VoiceMeeter Potato 3.1.2.2 builds.
- Creates and removes a marked localhost route and short-lived TLS certificate.
- Uses only the Python standard library at runtime.

## Supported binaries

| Architecture | File | Required SHA-256 |
|---|---|---|
| x86 | `voicemeeter8.exe` | `E1F2CDF2990FDF3D96057E18FE441E81F91385B5F63F87A6432B8B3708B92520` |
| x64 | `voicemeeter8x64.exe` | `738C876013EAA7EF09C42C4F156B68FBE98A8EB702160EC920D855CE2E8FB2BD` |

Unknown or modified files are rejected. No fuzzy matching is performed.

## Quick start

Read [HOW-TO-USE.md](HOW-TO-USE.md) before changing local routing or trust.
The abbreviated workflow is:

```powershell
# Verify that the installed executable is the supported original.
python .\patch_client.py status
python .\launch_patched.py --target x86 --dry-run

# Run once from elevated PowerShell.
.\setup_lab_route.ps1

# Terminal 1: keep the HTTPS emulator running.
python .\server.py --host 127.0.0.1 --port 443 `
  --cert .\lab-cert.pem --key .\lab-key.pem `
  --config .\config.example.json

# Terminal 2: fully close old VoiceMeeter processes, then launch.
python .\launch_patched.py --target x86
```

The example configuration uses `grant` mode and returns
`>AERO-LAB-GRANT<` for every non-empty `cmd`. The response is not vendor-signed;
the matching in-memory patch routes the client into its existing success block.

Remove the local route when testing is complete:

```powershell
.\remove_lab_route.ps1
```

## Server modes

Copy `config.example.json` and select one mode:

- `error`: return the configured `ERROR...` reply.
- `grant`: return `grant_reply` for every non-empty command.
- `fixed`: return the exact contents of `fixed_response_file`.
- `replay`: return a response selected by the SHA-256 of the URL-decoded
  command value.

The server cannot decrypt new request envelopes or create vendor-valid
certificates because the corresponding private keys are not present in the
client.

## Tests

Run the standard-library test suite on Windows:

```powershell
python -m unittest -v test_emulator.py
python -m compileall -q .
```

The GitHub Actions workflow runs these checks against Python 3.10 through 3.13
and validates both PowerShell scripts and the JSON examples.

## Documentation

- [HOW-TO-USE.md](HOW-TO-USE.md) — complete setup, usage, cleanup, and troubleshooting
- [PROTOCOL.md](PROTOCOL.md) — recovered request and response protocol
- [PATCH.md](PATCH.md) — supported hashes, offsets, byte changes, and launcher behavior
- [PUBLISHING.md](PUBLISHING.md) — final checks, remote setup, and first-release steps
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution and validation requirements
- [SECURITY.md](SECURITY.md) — safe reporting and sensitive-data guidance

## Repository layout

```text
.
|-- .github/                 GitHub Actions and contribution templates
|-- server.py                Local protocol emulator
|-- launch_patched.py        Recommended in-memory launcher
|-- patch_client.py          Static status/apply/restore research utility
|-- setup_lab_route.ps1      Local TLS and hosts-route setup
|-- remove_lab_route.ps1     Route and trust cleanup
|-- test_emulator.py         Unit tests
|-- config.example.json      Grant-mode example configuration
|-- replay-map.example.json  Replay-map schema example
`-- *.md                     Usage and research documentation
```

## Safety notes

- The hosts override affects all applications while it is installed.
- Do not browse the real VB-Audio shop while the override is active.
- `lab-key.pem` is an unencrypted local private key and is ignored by Git.
- The recommended launcher leaves the executable and Authenticode signature
  unchanged; its process-memory modification disappears on exit.
- Never commit VoiceMeeter executables, captured customer certificates, request
  envelopes, generated keys, or `.aero-original` backups.

VoiceMeeter and VB-Audio are trademarks of their respective owner. This project
is independent and is not affiliated with or endorsed by VB-Audio.

## AI assistance disclaimer

This project, including its source code and documentation, was created with
assistance from OpenAI Codex. AI-generated output may contain mistakes or
incomplete assumptions. The repository has been reviewed and tested for its
documented lab use, but users remain responsible for independently verifying
the code and using it only in environments where they have authorization.

## License

The original code and documentation in this repository are available under the
[MIT License](LICENSE). That license does not apply to VoiceMeeter or any other
third-party software.
