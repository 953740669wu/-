$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$revisionRoot = $PSScriptRoot
$config = Get-Content -LiteralPath (Join-Path $revisionRoot 'config.json') -Raw | ConvertFrom-Json
$transportDir = Join-Path $revisionRoot ('evidence\transport_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
New-Item -ItemType Directory -Path $transportDir | Out-Null
$statusPath = Join-Path $revisionRoot 'evidence\interactive_status.json'
function Write-Status($stage, $detail) {
    @{ stage = $stage; detail = $detail; transport = $transportDir; utc = [DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
}
try {
    Write-Status 'AWAITING_AUTHENTICATION' 'Enter SSH password in this window only. No password is saved.'
    Write-Host 'S01: Enter your SSH password below. Input is hidden and is not saved.'
    Write-Host 'Only short Bash/Linux stdlib checks will run. No torch, model, HBM or job submission.'
    $remoteSource = [IO.File]::ReadAllBytes((Join-Path $revisionRoot 'remote_protocol.py'))
    $remoteEncoded = [Convert]::ToBase64String($remoteSource)
    $remoteCommand = 'python3 -c "import base64;exec(base64.b64decode(' + "'" + $remoteEncoded + "'" + '))"'
    $sshArgs = @('-o', 'PubkeyAuthentication=no', '-o', 'StrictHostKeyChecking=yes',
        '-o', ('UserKnownHostsFile=' + $config.known_hosts), '-o', 'ConnectTimeout=12',
        '-o', 'NumberOfPasswordPrompts=1', '-o', 'ServerAliveInterval=15',
        '-o', 'ServerAliveCountMax=2', 'dengqingtian@10.44.9.4', $remoteCommand)
    $packageLine = [Convert]::ToBase64String([IO.File]::ReadAllBytes($config.package))
    $outputPath = Join-Path $transportDir 'transport.txt'
    $packageLine | & 'C:\Windows\System32\OpenSSH\ssh.exe' @sshArgs |
        Set-Content -LiteralPath $outputPath -Encoding utf8
    $sshExit = $LASTEXITCODE
    Write-Status 'SSH_EXITED' ('SSH exit code: ' + $sshExit)
    $workRoot = Split-Path (Split-Path $revisionRoot -Parent) -Parent
    $receivedPath = Join-Path $workRoot ('linux_return_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
    & $config.python -B (Join-Path $revisionRoot 'import_received.py') $outputPath $receivedPath
    if ($LASTEXITCODE -ne 0) { throw 'No valid evidence transport was received; inspect this window for authentication/transport error.' }
    Write-Status 'FINISHED' ('Evidence imported; SSH exit code: ' + $sshExit)
    Write-Host 'S01: Evidence returned. This window can be closed.'
} catch {
    Write-Status 'FAILED' $_.Exception.Message
    Write-Host ('S01: ' + $_.Exception.Message) -ForegroundColor Red
}
Read-Host 'Press Enter to close' | Out-Null
