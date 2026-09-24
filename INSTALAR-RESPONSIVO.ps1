param(
    [string]$AppPath = "C:\NurseTec-Apps\UniqueApp",
    [string]$ServiceName = "UniqueApp"
)

$ErrorActionPreference = "Stop"
$ReleasePath = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = "C:\NurseTec-Apps\Backups\AppResponsivo-$Timestamp"

Write-Host "Criando backup em $BackupPath"
New-Item -ItemType Directory -Force $BackupPath | Out-Null

Copy-Item "$AppPath\templates" "$BackupPath\templates" -Recurse -Force
Copy-Item "$AppPath\static\css\style.css" "$BackupPath\style.css" -Force
if (Test-Path "$AppPath\static\css\mobile-responsive.css") {
    Copy-Item "$AppPath\static\css\mobile-responsive.css" "$BackupPath\mobile-responsive.css" -Force
}
if (Test-Path "$AppPath\static\js\mobile-responsive.js") {
    Copy-Item "$AppPath\static\js\mobile-responsive.js" "$BackupPath\mobile-responsive.js" -Force
}

Write-Host "Parando serviço $ServiceName"
Stop-Service $ServiceName -ErrorAction Stop

try {
    Copy-Item "$ReleasePath\templates\*" "$AppPath\templates\" -Recurse -Force

    New-Item -ItemType Directory -Force "$AppPath\static\css" | Out-Null
    New-Item -ItemType Directory -Force "$AppPath\static\js" | Out-Null

    Copy-Item "$ReleasePath\static\css\mobile-responsive.css" "$AppPath\static\css\" -Force
    Copy-Item "$ReleasePath\static\js\mobile-responsive.js" "$AppPath\static\js\" -Force
    Copy-Item "$ReleasePath\static\js\configuracoes.js" "$AppPath\static\js\" -Force

    Push-Location $AppPath
    & ".\venv\Scripts\python.exe" -c "from app import app; [app.jinja_env.get_template(x) for x in ('base.html','index.html','prontuarios.html','alimentacao.html','relatorios.html','configuracoes.html','modais_configuracoes.html','detalhes_prontuario.html','login.html','register.html')]; print('TEMPLATES RESPONSIVOS OK')"
    Pop-Location

    Start-Service $ServiceName
    Start-Sleep -Seconds 3

    $Service = Get-Service $ServiceName
    if ($Service.Status -ne "Running") {
        throw "O serviço não permaneceu em execução."
    }

    Write-Host "Atualização responsiva instalada com sucesso." -ForegroundColor Green
    Write-Host "Backup: $BackupPath"
}
catch {
    Write-Host "Falha: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "O serviço será reiniciado. Use o backup para restaurar os arquivos."
    Start-Service $ServiceName -ErrorAction SilentlyContinue
    throw
}
