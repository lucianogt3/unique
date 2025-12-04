# === CONFIGURAÇÕES ===
$projectPath = "C:\Users\meu computador\Projetos\auditoria_hospitalar"
$pythonExe   = "C:\Users\meu computador\AppData\Local\Programs\Python\Python313\python.exe"
$logFile     = "C:\logs\auditoria\auditoria.log"

# Cria pasta de log se não existir
if (!(Test-Path (Split-Path $logFile))) {
    New-Item -ItemType Directory -Path (Split-Path $logFile) | Out-Null
}

# Roda infinitamente o servidor, reiniciando se cair
while ($true) {
    try {
        Write-Output "$(Get-Date) - Iniciando servidor Auditoria..." | Tee-Object -FilePath $logFile -Append
        Start-Process -FilePath $pythonExe -ArgumentList "-m waitress --listen=127.0.0.1:5006 app:app" -WorkingDirectory $projectPath -NoNewWindow -Wait
    } catch {
        Write-Output "$(Get-Date) - Erro detectado: $_" | Tee-Object -FilePath $logFile -Append
    }
    Write-Output "$(Get-Date) - Reiniciando servidor em 5 segundos..." | Tee-Object -FilePath $logFile -Append
    Start-Sleep -Seconds 5
}
