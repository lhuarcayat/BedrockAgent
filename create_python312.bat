@echo off
echo Buscando python.exe en venv...

set PYTHON_EXE=venv\python.exe
set PYTHON312_EXE=venv\python3.12.exe

if not exist "%PYTHON_EXE%" (
    echo Error: No se encontro %PYTHON_EXE%
    pause
    exit /b 1
)

echo Encontrado: %PYTHON_EXE%
echo Creando copia como: %PYTHON312_EXE%

copy "%PYTHON_EXE%" "%PYTHON312_EXE%" >nul

if exist "%PYTHON312_EXE%" (
    echo Exito: python3.12.exe creado
    echo Verificando version:
    "%PYTHON312_EXE%" --version
) else (
    echo Error al crear python3.12.exe
)

pause