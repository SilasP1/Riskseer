Start-Process powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  "Set-Location 'C:\Users\WOOKI\Riskseer'; python main.py; python -m uvicorn api:app --reload"
)

Start-Process powershell.exe -ArgumentList @(
  '-NoExit',
  '-Command',
  "`$env:Path += ';C:\Program Files\nodejs'; Set-Location 'C:\Users\WOOKI\Riskseer\Riskseer Frontend'; & 'C:\Program Files\nodejs\npm.cmd' run dev"
)