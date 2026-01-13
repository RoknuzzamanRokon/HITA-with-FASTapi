@echo off
setlocal enabledelayedexpansion

REM Generate JSON files for all suppliers
REM Usage: generate_all_suppliers.bat [supplier_name|--all]

echo 🚀 Hotel Supplier JSON Generator
echo ================================

REM Check if we're in the right directory
if not exist "country_json_file.py" (
    echo ❌ Error: country_json_file.py not found in current directory
    echo Please run this script from the utils/helper directory
    pause
    exit /b 1
)

REM Function to show usage
if "%1"=="--help" goto :show_usage
if "%1"=="-h" goto :show_usage
if "%1"=="/?" goto :show_usage

REM Set start time
set start_time=%time%

echo ⏰ Started at: %date% %time%
echo.

REM Run the Python script with arguments
if "%1"=="" (
    echo ⚠️  WARNING: No arguments provided!
    echo � To process ALL suppliers, use: %0 --all
    echo 💡 To process specific supplier, use: %0 ^<supplier_name^>
    echo.
    echo 🔄 Processing default supplier (mgholiday) only...
    echo Press Ctrl+C to cancel or wait 5 seconds to continue...
    timeout /t 5 /nobreak >nul
    python country_json_file.py
) else if "%1"=="--all" (
    echo 🔄 Processing ALL 27 suppliers one by one...
    echo ⏰ This will take a long time (estimated 30+ minutes)
    echo Press Ctrl+C to cancel or wait 3 seconds to continue...
    timeout /t 3 /nobreak >nul
    python country_json_file.py --all
) else (
    echo 🔄 Processing single supplier: %1
    python country_json_file.py %1
)

REM Set end time
set end_time=%time%

echo.
echo ⏰ Completed at: %date% %end_time%

REM Check if the script was successful
if %errorlevel% equ 0 (
    echo ✅ Script completed successfully!
) else (
    echo ❌ Script failed with errors!
    pause
    exit /b 1
)

echo.
echo Press any key to exit...
pause >nul
goto :eof

:show_usage
echo Usage:
echo   %0                    # Process default supplier (mgholiday)
echo   %0 --all              # Process all suppliers
echo   %0 ^<supplier_name^>    # Process specific supplier
echo.
echo Available suppliers:
echo   hotelbeds, ean, agoda, mgholiday, restel, stuba,
echo   hyperguestdirect, tbohotel, goglobal, ratehawkhotel,
echo   grnconnect, juniperhotel, paximumhotel, oryxhotel,
echo   dotw, hotelston, letsflyhotel, illusionshotel,
echo   innstant, roomerang, mikihotel, adonishotel,
echo   w2mhotel, kiwihotel, rakuten, rnrhotel
pause
goto :eof