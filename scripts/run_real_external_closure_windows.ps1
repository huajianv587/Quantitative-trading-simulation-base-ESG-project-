param(
    [switch]$AuthOnly,
    [switch]$BrokerOnly,
    [switch]$Full,
    [switch]$SkipLive,
    [switch]$ConfirmLive,
    [string]$WriteReportDir = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\bin\python"),
    "python"
)

$PythonExe = $null
foreach ($candidate in $PythonCandidates) {
    if ($candidate -eq "python") {
        $resolved = Get-Command python -ErrorAction SilentlyContinue
        if ($resolved) {
            $PythonExe = $resolved.Source
            break
        }
    } elseif (Test-Path $candidate) {
        $PythonExe = $candidate
        break
    }
}

if (-not $PythonExe) {
    throw "Python executable not found."
}

$ArgsList = @(
    (Join-Path $ProjectRoot "scripts\real_external_closure.py")
)

if ($AuthOnly) { $ArgsList += "--auth-only" }
if ($BrokerOnly) { $ArgsList += "--broker-only" }
if ($Full) { $ArgsList += "--full" }
if ($SkipLive) { $ArgsList += "--skip-live" }
if ($ConfirmLive) { $ArgsList += "--confirm-live" }
if ($WriteReportDir) {
    $ArgsList += "--write-report-dir"
    $ArgsList += $WriteReportDir
}

Write-Host "Running real external closure with $PythonExe"
& $PythonExe @ArgsList
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host "Real external closure failed with exit code $ExitCode" -ForegroundColor Red
    exit $ExitCode
}

Write-Host "Real external closure finished successfully." -ForegroundColor Green
