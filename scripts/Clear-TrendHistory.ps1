$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$trendPath = Join-Path $repoRoot 'output\case_trend_history.json'

if (Test-Path -LiteralPath $trendPath) {
  Remove-Item -LiteralPath $trendPath -Force
  Write-Host "Cleared trend history:"
  Write-Host " - $trendPath"
} else {
  Write-Host "No trend history file found."
}
