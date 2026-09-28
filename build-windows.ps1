param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Crie a .venv e instale as dependencias do projeto antes do build.'
}

Push-Location $projectRoot
try {
    $originalPath = $env:PATH
    $pythonBase = (& $python -c 'import sys; print(sys.base_prefix)').Trim()
    try {
        # Other tools on PATH may provide an incompatible icuuc.dll. Qt must use Windows ICU.
        $env:PATH = @(
            (Split-Path -Parent $python),
            $pythonBase,
            (Join-Path $pythonBase 'Scripts'),
            (Join-Path $env:SystemRoot 'System32'),
            $env:SystemRoot
        ) -join ';'
        & $python -m PyInstaller --noconfirm --clean --onedir --windowed `
            --name STZLyricsOverlay `
            --icon 'app\assets\logo.ico' `
            --add-data 'app\assets\logo.ico;app\assets' `
            app\main.py
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou: $LASTEXITCODE" }
    } finally {
        $env:PATH = $originalPath
    }
    if (Test-Path -LiteralPath 'dist\STZLyricsOverlay\_internal\icuuc.dll') {
        throw 'O bundle incluiu icuuc.dll de terceiros; build interrompido.'
    }

    if (-not $SkipInstaller) {
        $iscc = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
            'C:\Program Files\Inno Setup 7\ISCC.exe'
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $iscc) { throw 'Inno Setup 7 nao encontrado. Use -SkipInstaller para gerar somente o app.' }
        $innoVersion = (& $iscc --version | Select-Object -First 1).Trim()
        if ($innoVersion -notmatch '^7\.') { throw "Esperado Inno Setup 7; encontrado $innoVersion" }
        Write-Host "Compilando com Inno Setup $innoVersion"
        & $iscc 'stzlyrics-overlay.iss'
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou: $LASTEXITCODE" }
    }
} finally {
    Pop-Location
}
