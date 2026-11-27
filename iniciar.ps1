$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$runtime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$container = 'memorias-web-pg18'
$database = docker ps -a --filter "name=^/${container}$" --format '{{.Names}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker no está disponible.' }
if (-not $database) {
    if (-not (Test-Path -LiteralPath '.runtime/db-password')) {
        Set-Content -LiteralPath '.runtime/db-password' -Value ([guid]::NewGuid().ToString('N')) -NoNewline
    }
    $env:POSTGRES_PASSWORD = Get-Content -Raw -LiteralPath '.runtime/db-password'
    docker run -d --name $container -e POSTGRES_PASSWORD -e POSTGRES_DB=memorias_web -p 127.0.0.1:15484:5432 postgres:18.4-bookworm | Out-Null
    $creado = $LASTEXITCODE
    Remove-Item Env:POSTGRES_PASSWORD
    if ($creado -ne 0) { throw 'No se pudo crear el contenedor de Memorias Web.' }
} else {
    docker start $container | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar la base de Memorias Web.' }
}
$ready = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    docker exec $container pg_isready -U postgres -d memorias_web | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'La base no terminó de arrancar.' }

$python = (Get-Command python.exe).Source
& $python -m backend.setup_local
if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar el esquema.' }
$env:MEMORIAS_DSN = (Get-Content -Raw -LiteralPath '.runtime/api-dsn').Trim()
if (-not (Get-NetTCPConnection -LocalPort 14801 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','14801' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$runtime/api.log" -RedirectStandardError "$runtime/api-error.log"
}
$frontend = Join-Path $PSScriptRoot 'frontend'
if (-not (Test-Path -LiteralPath "$frontend/node_modules/next")) {
    npm.cmd --prefix $frontend ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación del frontend.' }
}
if (-not (Get-NetTCPConnection -LocalPort 14500 -State Listen -ErrorAction SilentlyContinue)) {
    $command = 'dev'
    if (Test-Path -LiteralPath "$frontend/.next/BUILD_ID") { $command = 'start' }
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'node_modules/next/dist/bin/next',$command,'--hostname','127.0.0.1','--port','14500' -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "$runtime/web.log" -RedirectStandardError "$runtime/web-error.log"
}
Write-Output 'Aplicación: http://127.0.0.1:14500'
Write-Output "Accesos de demostración: $runtime\accesos.txt"
