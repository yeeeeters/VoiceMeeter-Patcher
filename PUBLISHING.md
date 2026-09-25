# Publishing Checklist

The repository is prepared for a first GitHub push. No remote is configured by
the project itself.

## Before publishing

1. Run the local checks:

   ```powershell
   python -m compileall -q .
   python -m unittest -v test_emulator.py
   ```

2. Confirm that generated lab material is not tracked:

   ```powershell
   git status --short
   git ls-files | Select-String -Pattern '\.(key|pem|pfx|p12|cer|crt)$|\.aero-original$'
   ```

3. Review the staged snapshot:

   ```powershell
   git diff --cached --check
   git status
   ```

## Add a GitHub remote and push

Create an empty repository on GitHub without generating a README, license, or
`.gitignore`, then run:

```powershell
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Replace `OWNER` and `REPOSITORY` with the actual destination. If a remote named
`origin` already exists, inspect it with `git remote -v` and update it only when
needed:

```powershell
git remote set-url origin https://github.com/OWNER/REPOSITORY.git
```

## Optional first release

After CI passes on GitHub:

```powershell
git tag -a v1.0.0 -m "Initial public release"
git push origin v1.0.0
```

Attach the generated source archive to the release if a downloadable snapshot
is useful. Never attach generated private keys, certificates, thumbprints,
patched executables, or vendor binaries.
