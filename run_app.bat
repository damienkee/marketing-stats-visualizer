@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_EXE=py"
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            set "PYTHON_EXE=python"
        ) else (
            echo No Python interpreter found.
            echo Install Python and dependencies first:
            echo   pip install -r requirements.txt
            pause
            exit /b 1
        )
    )
)

echo Starting Marketing Stats Visualizer...
echo Open http://localhost:8501 if your browser does not open automatically.

%PYTHON_EXE% -m streamlit run app.py --server.headless true
