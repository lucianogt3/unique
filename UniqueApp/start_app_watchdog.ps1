param(
  [Parameter(Mandatory=$true)][string]$Path,
  [Parameter(Mandatory=$true)][int]$Port,
  [string]$Target = "",          # ex: "app:app" ou "app:create_app()"
  [string]$AppFile = "app.py"
)

# logs
$logDir = "C:\logs\AppWatcher"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "watcher-$($env:COMPUTERNAME).log"

function Log($msg){
  $timestamp = (Get-Date).ToString('s')
  "$timestamp `t $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Set-Location $Path
Log "==== Watcher START ($Path) ===="

# loop infinito: inicia app e reinicia se sair
$attempt = 0
while ($true) {
  try {
    $attempt++
    Log "Starting app (attempt $attempt) at $Path"

    if ($Target -ne "") {
      # usar flask cli com target
      $cmd = "python -m flask run --host=0.0.0.0 --port=$Port"
      $env:FLASK_APP = $Target
      $env:FLASK_ENV = "production"
      Log "Exec: $cmd (FLASK_APP=$Target)"
      & python -m flask run --host=0.0.0.0 --port=$Port
      $exitCode = $LASTEXITCODE
    } elseif (Test-Path $AppFile) {
      Log "Exec: python $AppFile"
      & python $AppFile
      $exitCode = $LASTEXITCODE
    } else {
      Log "ERROR: Arquivo $AppFile não encontrado em $Path. Saindo."
      exit 1
    }

    Log "Process exited with code $exitCode"
  } catch {
    Log "Exception: $($_.Exception.Message)"
  }

  # backoff incremental (5s, 10s, 20s,... cap em 5min)
  $sleep = [Math]::Min(300, 5 * [Math]::Pow(2, [Math]::Min(6, $attempt)))
  Log "Sleeping $sleep seconds before restart"
  Start-Sleep -Seconds $sleep
}
