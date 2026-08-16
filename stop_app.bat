@echo off
setlocal

echo Stopping Streamlit servers running on port 8501...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    taskkill /PID %%P /F >nul 2>nul
)

echo Done.
