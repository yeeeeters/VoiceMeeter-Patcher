#Requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Marker = '# AERO-VOICEMEETER-LAB'
$HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$ThumbprintFile = Join-Path $PSScriptRoot 'lab-cert-thumbprint.txt'

$Lines = @(Get-Content -LiteralPath $HostsPath)
$Filtered = @($Lines | Where-Object { $_ -notmatch [regex]::Escape($Marker) })
[IO.File]::WriteAllLines($HostsPath, $Filtered, [Text.Encoding]::ASCII)

if (Test-Path -LiteralPath $ThumbprintFile) {
    $Thumbprint = (Get-Content -LiteralPath $ThumbprintFile -Raw).Trim()
    foreach ($StoreName in @('Root', 'My')) {
        $Item = "Cert:\CurrentUser\$StoreName\$Thumbprint"
        if (Test-Path -LiteralPath $Item) {
            Remove-Item -LiteralPath $Item -Force
        }
    }
}

Clear-DnsClientCache
Write-Host 'Local VoiceMeeter lab route and trust entry removed.'
