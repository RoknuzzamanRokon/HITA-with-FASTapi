@echo off
echo ============================================================
echo RESTARTING SERVER WITH NEW CODE
echo ============================================================
echo.

echo Step 1: Stopping current server...
taskkill /F /IM python.exe 2>nul
if %errorlevel% == 0 (
    echo   [OK] Server stopped
) else (
    echo   [INFO] No server was running
)

echo.
echo Step 2: Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo Step 3: Starting server with new code...
echo   Directory: %CD%
echo   Command: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
echo.
echo ============================================================
echo SERVER STARTING...
echo ============================================================
echo.
echo Look for this line in the output:
echo   "INFO: Export worker initialized"
echo.
echo If you see it, the new code is loaded!
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8001 --reload
