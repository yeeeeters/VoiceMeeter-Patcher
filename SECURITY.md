# Security Policy

## Supported code

Security fixes are applied to the current `main` branch. Client compatibility
is intentionally restricted to the hashes documented in `PATCH.md`.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when it is enabled for the
repository. If it is unavailable, contact the repository owner privately before
publishing details that could expose users or third-party systems.

Include the affected commit, Windows version, Python version, architecture, and
minimal reproduction steps. Do not include customer certificates, generated
private keys, raw activation envelopes, or personal machine identifiers.

## Expected behavior

The following are intentional and are not vulnerabilities in this repository:

- The lab server accepts arbitrary non-empty commands in `grant` mode.
- The launcher writes a version-locked patch into a process it creates.
- The setup script adds a marked hosts-file entry and a current-user root
  certificate after explicit elevation.
- The generated private key is stored unencrypted for use by the local Python
  TLS server.

Unexpected broad file matching, writes outside the documented targets,
unredacted secret logging, or persistence beyond the documented cleanup path
should be reported.
