param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "venv", "install", "run", "test", "clean", "docker-build", "docker-up", "docker-down")]
    [string]$Task = "help"
)

$ErrorActionPreference = "Stop"

$VenvDir = ".venv"
$PythonExe = Join-Path $VenvDir "Scripts/python.exe"
$PipExe = Join-Path $VenvDir "Scripts/pip.exe"
$App = "app.main:app"
$HostAddr = "127.0.0.1"
$Port = "8000"

function Ensure-Venv {
    if (-not (Test-Path $PythonExe)) {
        python -m venv $VenvDir
    }
}

function Show-Help {
    Write-Host "Usage: .\Makefile.ps1 <task>"
    Write-Host ""
    Write-Host "Tasks:"
    Write-Host "  help          Show this help"
    Write-Host "  venv          Create .venv"
    Write-Host "  install       Create .venv and install dependencies"
    Write-Host "  run           Start uvicorn (reload) on http://localhost:8000"
    Write-Host "  test          Run pytest"
    Write-Host "  clean         Clear runtime data (input/videos, outputs/converted, state.json)"
    Write-Host "  docker-build  docker compose build"
    Write-Host "  docker-up     docker compose up -d"
    Write-Host "  docker-down   docker compose down"
}

switch ($Task) {
    "help" {
        Show-Help
    }
    "venv" {
        Ensure-Venv
        Write-Host "Virtual environment is ready: $VenvDir"
    }
    "install" {
        Ensure-Venv
        & $PythonExe -m pip install --upgrade pip
        & $PipExe install -r requirements.txt
    }
    "run" {
        Ensure-Venv
        & $PythonExe -m uvicorn $App --reload --host $HostAddr --port $Port
    }
    "test" {
        Ensure-Venv
        & $PythonExe -m pytest -q
    }
    "clean" {
        if (Test-Path "input/videos") {
            Get-ChildItem "input/videos" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        }
        if (Test-Path "outputs/converted") {
            Get-ChildItem "outputs/converted" -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        }
        if (Test-Path "state.json") {
            Remove-Item "state.json" -Force
        }
    }
    "docker-build" {
        docker compose build
    }
    "docker-up" {
        docker compose up -d
    }
    "docker-down" {
        docker compose down
    }
}
