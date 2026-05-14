@echo off
echo ============================================================
echo  Mutual Fund FAQ Assistant - Phase 1.1 Setup
echo ============================================================
echo.

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Make sure Python is installed and in PATH.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browsers (Chromium)...
playwright install chromium
if %errorlevel% neq 0 (
    echo [ERROR] Playwright browser install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Creating output directories...
if not exist "data\raw" mkdir "data\raw"
if not exist "logs" mkdir "logs"

echo.
echo ============================================================
echo  Setup complete!
echo  Run the scraper with:  python src/scraper.py
echo  Validate output with:  python src/validate_scrape.py
echo ============================================================
pause
