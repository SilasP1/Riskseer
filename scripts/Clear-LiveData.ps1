$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot 'data'

$headers = @{
  'events.csv'  = 'event_id,event_time,lat,lon,source,intensity,event_type,equipment_type,contractor,work_type'
  'tickets.csv' = 'ticket_id,start_time,end_time,center_lat,center_lon,radius_m,contractor,work_type,status,submitted_at'
  'assets.csv'  = 'asset_id,asset_type,lat,lon'
  'field_reports.csv' = 'report_id,observed_at,lat,lon,narrative,equipment_type,work_method,reporter,contractor,photos_present,audio_present,video_present'
  'markings.csv' = 'marking_id,observed_at,lat,lon,ticket_id,utility_name,marking_state,locate_status,last_marked_at,last_refreshed_at,mark_confidence,refresh_required,partial_marks,clearly_visible'
  'positive_responses.csv' = 'response_id,observed_at,ticket_id,response_status,responder,response_code,clear_to_excavate,complete_response,conflict_flag'
}

foreach ($fileName in $headers.Keys) {
  $path = Join-Path $dataDir $fileName
  Set-Content -LiteralPath $path -Value $headers[$fileName] -Encoding utf8
}

Write-Host "Live input CSVs cleared:"
foreach ($fileName in $headers.Keys) {
  Write-Host " - $fileName"
}
