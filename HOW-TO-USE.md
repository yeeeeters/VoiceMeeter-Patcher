# How to Use the VoiceMeeter 3.1.2.2 License-Server Lab

This guide explains how to run the local grant server and launch VoiceMeeter
Potato 3.1.2.2 with the matching grant patch applied only to process memory.

The recommended workflow does **not** modify the installed executables. The
original signed file is launched suspended, ten bytes are changed in the new
process, and its initial thread is resumed. The memory patch disappears when
VoiceMeeter exits.

## Scope and supported version

This package is locked to these exact VoiceMeeter Potato 3.1.2.2 files:

| Architecture | File | Required original SHA-256 |
|---|---|---|
| 32-bit | `voicemeeter8.exe` | `E1F2CDF2990FDF3D96057E18FE441E81F91385B5F63F87A6432B8B3708B92520` |
| 64-bit | `voicemeeter8x64.exe` | `738C876013EAA7EF09C42C4F156B68FBE98A8EB702160EC920D855CE2E8FB2BD` |

Do not force the patch onto another release. The launcher intentionally refuses
unknown or modified files.

## What the components do

| File | Purpose |
|---|---|
| `server.py` | HTTPS emulator for VoiceMeeter's activation endpoint |
| `config.example.json` | Enables grant mode and defines the reply |
| `launch_patched.py` | Recommended launcher; patches only process memory |
| `patch_client.py` | Static patch/status/restore utility; not needed for the recommended workflow |
| `setup_lab_route.ps1` | Creates a local TLS certificate, trusts it, and routes the vendor hostname to localhost |
| `remove_lab_route.ps1` | Removes the marked hosts entry and lab certificate |
| `test_emulator.py` | Emulator tests |

In grant mode, every request with a non-empty `cmd` receives:

```text
>AERO-LAB-GRANT<
```

That is not a vendor-signed certificate. The in-memory client patch bypasses
the local certificate verification and enters VoiceMeeter's original success
block after the normal email and response inputs have been loaded.

## Requirements

- Windows with VoiceMeeter Potato 3.1.2.2 installed in the default directory.
- Python 3 available as `python`.
- Administrator access for the one-time certificate and hosts-file setup.
- The server terminal must remain open during activation.
- Use this only in an isolated test environment. While the route is active,
  `shop.vb-audio.com` resolves to the local computer.

## 1. Open the package directory

Extract the ZIP, then open PowerShell in the extracted directory. All commands
below assume that this directory contains `server.py`, `launch_patched.py`, and
the PowerShell setup scripts.

## 2. Ensure the installed files are original

Run:

```powershell
python .\patch_client.py status
```

Expected result:

```text
32-bit: original; ...
64-bit: original; ...
```

If either file says `patched` because the earlier static method was used, close
VoiceMeeter and restore the originals from an elevated PowerShell:

```powershell
python .\patch_client.py restore
python .\patch_client.py status
```

Do not continue if the status is `unknown`.

## 3. Verify the in-memory launcher

For the 32-bit program:

```powershell
python .\launch_patched.py --target x86 --dry-run
```

For the 64-bit program:

```powershell
python .\launch_patched.py --target x64 --dry-run
```

The result should say that the original was verified and that no process was
started.

Most VoiceMeeter Potato shortcuts launch the 32-bit `voicemeeter8.exe`, even on
64-bit Windows. Use `x86` unless you deliberately run
`voicemeeter8x64.exe`.

## 4. Install the local HTTPS route

This is normally required only once. Start an elevated PowerShell in the
package directory. One way to open it from the current window is:

```powershell
Start-Process powershell.exe -Verb RunAs -WorkingDirectory $PWD.Path `
  -ArgumentList '-NoExit','-ExecutionPolicy','Bypass'
```

Approve the UAC prompt. In the new Administrator window, run:

```powershell
.\setup_lab_route.ps1
```

The script performs the following actions:

1. Creates a 30-day self-signed TLS certificate for `shop.vb-audio.com`.
2. Saves its certificate and private key as `lab-cert.pem` and `lab-key.pem`.
3. Trusts the certificate in the current user's root certificate store.
4. Adds this marked line to the Windows hosts file:

   ```text
   127.0.0.1 shop.vb-audio.com # AERO-VOICEMEETER-LAB
   ```

5. Clears the Windows DNS cache.

Expected final output includes:

```text
Local route installed for shop.vb-audio.com.
```

The current script supports both Windows PowerShell 5.1 `RSACng` and modern
PowerShell/.NET private-key export APIs.

## 5. Start the grant server

In one PowerShell window, run:

```powershell
python .\server.py --host 127.0.0.1 --port 443 `
  --cert .\lab-cert.pem `
  --key .\lab-key.pem `
  --config .\config.example.json
```

Expected output:

```text
listening on https://127.0.0.1:443/en/module/vblicensing/certify mode=grant
```

Leave this terminal open. The server logs only the command length and SHA-256
fingerprint, not the encrypted command itself.

Optional endpoint check from another PowerShell window:

```powershell
$Reply = Invoke-WebRequest `
  -Uri 'https://shop.vb-audio.com/en/module/vblicensing/certify?cmd=probe' `
  -UseBasicParsing
$Reply.Content
```

Expected body:

```text
>AERO-LAB-GRANT<
```

If the machine uses a system proxy, configure a proxy bypass for
`shop.vb-audio.com` so that WinINet connects to `127.0.0.1`.

## 6. Fully close existing VoiceMeeter processes

VoiceMeeter may continue running without a visible main window. Check for an
existing process:

```powershell
Get-Process -Name 'voicemeeter8','voicemeeter8x64' -ErrorAction SilentlyContinue
```

Close it through the system-tray icon when possible. If it remains hidden, use:

```powershell
Get-Process -Name 'voicemeeter8','voicemeeter8x64' `
  -ErrorAction SilentlyContinue | Stop-Process -Force
```

Launching while an older instance exists can make the newly launched process
exit immediately because VoiceMeeter behaves as a single-instance application.

## 7. Launch VoiceMeeter with the memory patch

Open a second terminal in the package directory while the server continues to
run.

For the normal 32-bit executable:

```powershell
python .\launch_patched.py --target x86
```

For the explicitly selected 64-bit executable:

```powershell
python .\launch_patched.py --target x64
```

Successful output looks like:

```text
launched 32-bit VoiceMeeter PID=12345; in-memory patch address=0x12360A0
```

The address changes because of ASLR. The launcher verifies the runtime bytes,
changes page protection only for the write, flushes the instruction cache,
restores the original page protection, and then resumes the process.

If VoiceMeeter is running but no window appears, open it through its system-tray
icon. A process with no `MainWindowHandle` can still be healthy and responsive.

## 8. Submit an activation request

In VoiceMeeter, open the License Activation dialog and enter syntactically valid
values. For example:

```text
Email:    lab@example.invalid
Response: AAAAAAAAAA
```

The response must contain exactly ten characters because that UI validation
happens before the patched decision point.

Submit the request. The expected flow is:

1. VoiceMeeter creates its encrypted `cmd` request.
2. Windows resolves `shop.vb-audio.com` to `127.0.0.1`.
3. The trusted lab certificate completes the HTTPS connection.
4. The emulator replies with `>AERO-LAB-GRANT<`.
5. VoiceMeeter stores the reply as `LicenseCertificate`.
6. The in-memory patch skips the local signature/challenge checks.
7. VoiceMeeter executes its existing activation-success block.

## 9. Starting VoiceMeeter again later

The process patch is not persistent. After closing VoiceMeeter or rebooting,
start the server and use the launcher again:

```powershell
python .\launch_patched.py --target x86
```

Starting VoiceMeeter normally uses the original unmodified verifier, so the
dummy lab response will not validate.

## 10. Shut down and remove the lab route

1. Close VoiceMeeter.
2. Stop `server.py` with `Ctrl+C` in its terminal.
3. Open elevated PowerShell in the package directory.
4. Run:

   ```powershell
   .\remove_lab_route.ps1
   ```

This removes only the marked hosts-file line and the recorded certificate from
the current user's `Root` and `My` stores.

The PEM files remain in the package directory for reuse. After removing the
route, they can also be deleted if no longer needed:

```powershell
Remove-Item -LiteralPath .\lab-cert.pem,.\lab-key.pem,.\lab-cert-thumbprint.txt
```

## Verification commands

Confirm that the installed binaries remain original:

```powershell
Get-FileHash -Algorithm SHA256 `
  'C:\Program Files (x86)\VB\Voicemeeter\voicemeeter8.exe', `
  'C:\Program Files (x86)\VB\Voicemeeter\voicemeeter8x64.exe'
```

Check the local route:

```powershell
Select-String `
  -LiteralPath "$env:SystemRoot\System32\drivers\etc\hosts" `
  -Pattern 'AERO-VOICEMEETER-LAB'
```

Check whether the server owns port 443:

```powershell
Get-NetTCPConnection -LocalPort 443 -State Listen
```

Check the VoiceMeeter process:

```powershell
Get-Process -Name 'voicemeeter8','voicemeeter8x64' `
  -ErrorAction SilentlyContinue | `
  Select-Object Id,ProcessName,Responding,StartTime
```

## Troubleshooting

### `#requires` says PowerShell is not running as Administrator

Only the route setup/removal needs elevation. Open Administrator PowerShell as
shown in step 4 and run the script there.

### `RSACng` has no `ExportPkcs8PrivateKey` method

That error came from an older setup script. Use the current
`setup_lab_route.ps1`, which falls back to
`CngKeyBlobFormat.Pkcs8PrivateBlob` under Windows PowerShell 5.1.

### Error 299 from `CreateToolhelp32Snapshot`

That error came from an older launcher when 64-bit Python targeted the 32-bit
VoiceMeeter process. The current launcher reads the image base from the WOW64
PEB through `ProcessWow64Information` and does not depend on module enumeration
for this case.

### The launcher reports `binary state is patched`

Restore the original file first:

```powershell
python .\patch_client.py restore
python .\patch_client.py status
```

Then use `launch_patched.py`.

### The launcher reports `binary state is unknown`

The installed version or file contents do not match the supported build. Do not
force the offsets. Reinstall the exact supported version or reverse and validate
the new build separately.

### Port 443 is already in use

Find the owner:

```powershell
$Connection = Get-NetTCPConnection -LocalPort 443 -State Listen
Get-Process -Id $Connection.OwningProcess
```

Stop or reconfigure only the known conflicting service. VoiceMeeter itself is
hard-coded to HTTPS port 443, so running this emulator on another port will not
work without an additional client change.

### TLS or connection error

Verify all of the following:

- `server.py` is still running.
- `lab-cert.pem` and `lab-key.pem` exist.
- The marked hosts entry is present.
- The setup script completed under the same Windows user running VoiceMeeter.
- No WinINet/system proxy is intercepting or bypassing the localhost route.
- Local firewall policy permits the Python listener on TCP port 443.

### VoiceMeeter appears to do nothing when launched

Check Task Manager or `Get-Process`. VoiceMeeter may be running in the system
tray without a visible window. Also ensure that an older instance was fully
closed before using the launcher.

### VoiceMeeter starts normally but rejects the lab response

It was probably started from the normal shortcut rather than through
`launch_patched.py`, or the patched process exited and a different instance was
opened. Fully close all VoiceMeeter processes and repeat step 7.

## Security and cleanup notes

- Grant mode accepts every non-empty encrypted activation command.
- The hosts override affects all applications on the test machine while active.
- Do not browse the real VB-Audio shop while the override is installed.
- `lab-key.pem` is an unencrypted private key and should remain local.
- Remove the route and trust entry after testing.
- The recommended workflow leaves the installed executable and its Authenticode
  signature unchanged.
