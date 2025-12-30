@echo off
echo ============================================================
echo STARTING SERVER WITH PIPENV
echo ============================================================
echo.
echo Stopping any existing servers...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Starting server with pipenv...
echo.
echo IMPORTANT: Look for these lines in the output:
echo   "INFO: Export worker initialized"
echo   "INFO: ExportWorker initialized: max_workers=3"
echo.
echo If you see these, the new code is loaded!
echo If you DON'T see these, there's an error.
echo.
echo ============================================================
echo.

pipenv run uvicorn main:app --host 0.0.0.0 --port 8001 --reload
