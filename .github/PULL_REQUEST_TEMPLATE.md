## Summary

Describe the problem and the focused change.

## Validation

- [ ] `python -m compileall -q .`
- [ ] `python -m unittest -v test_emulator.py`
- [ ] PowerShell scripts parse without errors
- [ ] Documentation reflects behavioral or compatibility changes
- [ ] No binaries, keys, certificates, activation data, or machine identifiers are included

## Version-specific changes

If client compatibility changed, list the exact version, architecture, SHA-256,
RVA, expected bytes, replacement bytes, and control-flow justification.
