#Requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$LabHostName = 'shop.vb-audio.com'
$Marker = '# AERO-VOICEMEETER-LAB'
$HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$HostsBackup = "$HostsPath.voicemeeter-lab-backup"
$CertPem = Join-Path $PSScriptRoot 'lab-cert.pem'
$KeyPem = Join-Path $PSScriptRoot 'lab-key.pem'
$ThumbprintFile = Join-Path $PSScriptRoot 'lab-cert-thumbprint.txt'

function ConvertTo-Pem([string]$Label, [byte[]]$Bytes) {
    $Body = [Convert]::ToBase64String(
        $Bytes,
        [Base64FormattingOptions]::InsertLineBreaks
    )
    return "-----BEGIN $Label-----`r`n$Body`r`n-----END $Label-----`r`n"
}

$Cert = $null
if (Test-Path -LiteralPath $ThumbprintFile) {
    $OldThumbprint = (Get-Content -LiteralPath $ThumbprintFile -Raw).Trim()
    $Cert = Get-Item -LiteralPath "Cert:\CurrentUser\My\$OldThumbprint" -ErrorAction SilentlyContinue
}

if ($null -eq $Cert -or $Cert.NotAfter -le (Get-Date).AddDays(1)) {
    $Cert = New-SelfSignedCertificate `
        -DnsName $LabHostName `
        -Subject "CN=$LabHostName, O=AERO Local Lab" `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -Type SSLServerAuthentication `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -KeyExportPolicy Exportable `
        -NotAfter (Get-Date).AddDays(30)
    Set-Content -LiteralPath $ThumbprintFile -Value $Cert.Thumbprint -Encoding ascii
}

$CertificateDer = $Cert.Export(
    [System.Security.Cryptography.X509Certificates.X509ContentType]::Cert
)
$Rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($Cert)
try {
    if ($null -ne $Rsa.GetType().GetMethod('ExportPkcs8PrivateKey', [Type[]]@())) {
        # PowerShell 7 / modern .NET.
        $PrivateKeyDer = $Rsa.ExportPkcs8PrivateKey()
    } elseif ($Rsa -is [System.Security.Cryptography.RSACng]) {
        # Windows PowerShell 5.1 / .NET Framework exposes the same export
        # through the underlying CNG key.
        $PrivateKeyDer = $Rsa.Key.Export(
            [System.Security.Cryptography.CngKeyBlobFormat]::Pkcs8PrivateBlob
        )
    } else {
        throw "Unsupported RSA provider: $($Rsa.GetType().FullName)"
    }
} finally {
    $Rsa.Dispose()
}
[IO.File]::WriteAllText($CertPem, (ConvertTo-Pem 'CERTIFICATE' $CertificateDer), [Text.Encoding]::ASCII)
[IO.File]::WriteAllText($KeyPem, (ConvertTo-Pem 'PRIVATE KEY' $PrivateKeyDer), [Text.Encoding]::ASCII)

$RootStore = [System.Security.Cryptography.X509Certificates.X509Store]::new(
    'Root',
    [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
)
try {
    $RootStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $AlreadyTrusted = $RootStore.Certificates.Find(
        [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
        $Cert.Thumbprint,
        $false
    )
    if ($AlreadyTrusted.Count -eq 0) {
        $RootStore.Add($Cert)
    }
} finally {
    $RootStore.Close()
}

$Lines = @(Get-Content -LiteralPath $HostsPath)
$Conflicts = @($Lines | Where-Object {
    $_ -notmatch [regex]::Escape($Marker) -and
    $_ -notmatch '^\s*#' -and
    $_ -match "(^|\s)$([regex]::Escape($LabHostName))(\s|$)"
})
if ($Conflicts.Count -gt 0) {
    throw "The hosts file already has an unmanaged entry for $LabHostName. Remove it manually before continuing."
}
if (-not (Test-Path -LiteralPath $HostsBackup)) {
    Copy-Item -LiteralPath $HostsPath -Destination $HostsBackup
}
if (-not ($Lines | Where-Object { $_ -match [regex]::Escape($Marker) })) {
    Add-Content -LiteralPath $HostsPath -Value "127.0.0.1 $LabHostName $Marker" -Encoding ascii
}

Clear-DnsClientCache
Write-Host "Local route installed for $LabHostName."
Write-Host "Certificate: $CertPem"
Write-Host "Private key: $KeyPem"
Write-Warning 'Normal access to shop.vb-audio.com is redirected while this route is installed.'
