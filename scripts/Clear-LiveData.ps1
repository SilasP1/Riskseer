$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot 'data'

$headers = @{
  'events.csv'  = 'event_id,event_time,lat,lon,source,intensity,event_type,equipment_type'
  'tickets.csv' = 'ticket_id,start_time,end_time,center_lat,center_lon,radius_m,contractor,work_type,status'
  'assets.csv'  = 'asset_id,asset_type,lat,lon'
}

foreach ($fileName in $headers.Keys) {
  $path = Join-Path $dataDir $fileName
  Set-Content -LiteralPath $path -Value $headers[$fileName] -Encoding utf8
}

Write-Host "Live input CSVs cleared:"
foreach ($fileName in $headers.Keys) {
  Write-Host " - $fileName"
}
