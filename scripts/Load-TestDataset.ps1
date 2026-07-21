param(
  [string]$DatasetName = 'default'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot 'data'
$datasetDir = Join-Path $dataDir "test_data\$DatasetName"

if (-not (Test-Path -LiteralPath $datasetDir)) {
  throw "Test dataset '$DatasetName' was not found at $datasetDir"
}

$requiredFiles = @('events.csv', 'tickets.csv', 'assets.csv')

foreach ($fileName in $requiredFiles) {
  $sourcePath = Join-Path $datasetDir $fileName
  $targetPath = Join-Path $dataDir $fileName

  if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Missing required dataset file: $sourcePath"
  }

  Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
}

Write-Host "Loaded test dataset '$DatasetName' into live data inputs."
Write-Host "Files copied:"
foreach ($fileName in $requiredFiles) {
  Write-Host " - $fileName"
}
