@echo off
rem VizPlay para Windows (PySide6 + QML).
rem La primera vez crea el entorno de Python e instala lo que falta; las
rem siguientes arranca directamente. Si ya está abierta, la trae al frente
rem (la propia app se encarga: instancia única).
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Preparando VizPlay por primera vez: creando el entorno de Python...
    where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo No se ha podido crear el entorno. Hace falta Python 3.10 o posterior:
        echo   https://www.python.org/downloads/  ^(marca "Add python.exe to PATH"^)
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import PySide6.QtMultimedia, PySide6.QtQuick, requests" >nul 2>nul
if errorlevel 1 (
    echo Instalando lo que necesita VizPlay ^(solo la primera vez, unos minutos^)...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r escritorio\requirements.txt
    if errorlevel 1 (
        echo.
        echo No se ha podido instalar. Revisa la conexion a Internet y vuelve a probar.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" -m escritorio
endlocal
