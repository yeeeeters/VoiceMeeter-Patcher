# VoiceMeeter 3.1.2.2 activation protocol notes

Target analyzed: `voicemeeter8.exe` / `voicemeeter8x64.exe`, version 3.1.2.2.

## Request

- Transport: HTTPS to TCP port 443 through WinINet.
- Host: `shop.vb-audio.com`
- Path: `/en/module/vblicensing/certify`
- Method: `GET`
- Query: exactly one `cmd=<opaque encrypted envelope>` parameter.
- User agent: `VB-Audio License Authentication Service`.

The client creates a fresh randomized envelope for every online activation. The
plaintext includes the product ID, a system/application identifier, lower-case
email, and the upper-case ten-character response. It is transformed using the
embedded public key before URL encoding. A standalone emulator cannot decrypt
that envelope without the corresponding server private key.

## Response

The client treats the response body as application-level text:

- First byte `>`: candidate license certificate. The body is stored as
  `LicenseCertificate` and then checked locally.
- Prefix `ERROR`: server error text shown by the activation UI.
- Anything else: malformed/unexpected server reply.

HTTP success alone does not activate the product. A `>` response must also pass
the local public-key certificate verifier and match the expected activation
tuple. Consequently, this emulator can reproduce framing, error behavior, and
captured-response replay, but it cannot mint new valid certificates without the
vendor's signing private key.

The package's explicit grant-all mode pairs a dummy `>` response with a
version-locked client patch. That patch bypasses the verifier call and its
challenge comparison after the normal UI and registry inputs have been loaded,
then enters the application's existing success block. It does not recover or
forge the vendor key.

## Relevant 32-bit client locations

- Online worker: static VA `0x00426550`
- Embedded endpoint decoder: static VA `0x00426340`
- Public-key transform: static VA `0x00413D10`
- Server-link object fields: pointer at `+0x1594`, length at `+0x1598`

The endpoint was recovered by emulating the decoder against the initialized
memory of the running 32-bit process. No request was sent to the vendor service.
