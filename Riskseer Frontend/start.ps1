$frontendDir = $PSScriptRoot
$repoRoot = Split-Path -Parent $frontendDir

Start-Process powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  "Set-Location '$repoRoot'; python main.py; python -m uvicorn api:app --reload"
)

Start-Process powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  "Set-Location '$frontendDir'; npm run dev"
)
