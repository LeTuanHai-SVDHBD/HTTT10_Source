# Run from PowerShell; requires Docker Desktop with Linux containers.
# Only the separate httt10-tests project is removed during cleanup.
param([switch]$SkipFrontendBuild)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$testCompose = Join-Path $repo "compose.test.yaml"
$code = 1
$summary = Join-Path $repo "verification/summary.json"
if (Test-Path $summary) { Remove-Item $summary }
try {
    Get-Command docker -ErrorAction Stop | Out-Null
    & docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw "Docker Desktop chua san sang. Mo Docker Desktop voi Linux containers." }
    if (-not $SkipFrontendBuild) {
        & docker build -t httt10-frontend-check (Join-Path $repo "frontend")
        if ($LASTEXITCODE -ne 0) { throw "Frontend image build failed." }
    }
    & docker compose -p httt10-tests -f $testCompose up --build --abort-on-container-exit --exit-code-from tests
    $code = $LASTEXITCODE
    if ($code -eq 0) { Write-Host "PASS. Xem verification/summary.json. Can kiem thu thu cong theo README.md." }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
} finally {
    # This does not touch the website's project or its data volumes.
    & docker compose -p httt10-tests -f $testCompose down -v
}
exit $code
