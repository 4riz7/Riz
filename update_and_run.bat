@echo off
echo Pulling latest changes from GitHub...
git pull origin main
echo.
echo Starting the bot...
python main.py
echo.
echo Bot stopped.
pause
