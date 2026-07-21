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
$optionalFiles = @('field_reports.csv', 'markings.csv', 'positive_responses.csv')

foreach ($fileName in $requiredFiles) {
  $sourcePath = Join-Path $datasetDir $fileName
  $targetPath = Join-Path $dataDir $fileName

  if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Missing required dataset file: $sourcePath"
  }

  Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
}

foreach ($fileName in $optionalFiles) {
  $sourcePath = Join-Path $datasetDir $fileName
  $targetPath = Join-Path $dataDir $fileName
  if (Test-Path -LiteralPath $sourcePath) {
    Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
  } elseif (Test-Path -LiteralPath $targetPath) {
    $header = Get-Content -LiteralPath $targetPath -TotalCount 1
    Set-Content -LiteralPath $targetPath -Value $header -Encoding utf8
  }
}

Write-Host "Loaded test dataset '$DatasetName' into live data inputs."
Write-Host "Files copied:"
foreach ($fileName in ($requiredFiles + $optionalFiles)) {
  if (-not (Test-Path -LiteralPath (Join-Path $datasetDir $fileName))) { continue }
  Write-Host " - $fileName"
}
