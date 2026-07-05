@echo off
cd /d "%~dp0"

echo [1/2] Starting Flask server (web_app.py)...
echo   - index.html will open automatically in your browser once the server is up.
echo   - Closing this window will stop the server.
echo.

python web_app.py

echo.
echo [ERROR] Server has stopped. Check the messages above.
pause
