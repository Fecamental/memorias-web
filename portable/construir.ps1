param(
    [string]$BuildRoot = (Join-Path $env:LOCALAPPDATA 'MemoriasWebBuild'),
    [string]$CrtDir = (Join-Path $env:WINDIR 'System32')
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
$BuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
$py = Join-Path $BuildRoot 'venv/Scripts/python.exe'
$pgZip = Join-Path $BuildRoot 'postgresql-18.7-2.zip'
$pg = Join-Path $BuildRoot 'postgresql'
$licencias = Join-Path $BuildRoot 'licencias'
$web = Join-Path $repo 'frontend/.next-portable'
$destino = Join-Path $BuildRoot 'dist'

if (-not (Test-Path -LiteralPath $py)) {
    uv venv --python 3.14 (Join-Path $BuildRoot 'venv')
    if ($LASTEXITCODE) { throw 'Falló la creación del entorno de compilación.' }
}
uv pip install --link-mode copy --python $py -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE) { throw 'No se instalaron las dependencias de compilación.' }
if (-not (Test-Path -LiteralPath $pgZip)) {
    curl.exe --fail --silent --show-error --location --retry 2 -o $pgZip 'https://get.enterprisedb.com/postgresql/postgresql-18.7-2-windows-x64-binaries.zip'
    if ($LASTEXITCODE) { throw 'Falló la descarga de PostgreSQL.' }
}
& $py portable/preparar_postgres.py $pgZip $pg $CrtDir
if ($LASTEXITCODE) { throw 'Falló la preparación de PostgreSQL.' }
& $py portable/licencias.py $licencias (Join-Path $repo 'frontend')
if ($LASTEXITCODE) { throw 'Falló la recopilación de licencias.' }

if (-not (Test-Path -LiteralPath 'frontend/node_modules/next')) {
    npm.cmd --prefix frontend ci --no-fund --no-audit
    if ($LASTEXITCODE) { throw 'Falló la instalación del frontend.' }
}
$env:MEMORIAS_STATIC = '1'
try {
    npm.cmd --prefix frontend run build
    if ($LASTEXITCODE) { throw 'Falló la exportación estática.' }
} finally {
    Remove-Item Env:MEMORIAS_STATIC
}
if (-not (Test-Path -LiteralPath (Join-Path $web 'index.html'))) {
    throw 'No se encontró la interfaz exportada.'
}
& $py -m PyInstaller --noconfirm --clean --onefile --console --noupx `
    --name 'MemoriasWeb-Windows-x64' --distpath $destino `
    --workpath (Join-Path $BuildRoot 'pyinstaller') --specpath $BuildRoot `
    --paths $repo --collect-submodules asyncpg `
    --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.lifespan.on --hidden-import uvicorn.logging `
    --add-data "$web;web" --add-data "$pg;postgresql" --add-data "$licencias;licencias" `
    --add-data "$(Join-Path $repo 'backend/catalogo.json');backend" --add-data "$(Join-Path $repo 'backend/catalogo_v1.json');backend" `
    --add-data "$(Join-Path $repo 'database/001_inicial.sql');database" `
    portable/arranque.py
if ($LASTEXITCODE) { throw 'Falló el empaquetado del ejecutable.' }
Get-Item -LiteralPath (Join-Path $destino 'MemoriasWeb-Windows-x64.exe') | Select-Object FullName,Length
