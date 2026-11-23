@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (echo Python 3.10+ required & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (echo Cannot install dependencies. Check internet access & pause & exit /b 1)
set ARAK_DEVELOPMENT=1
python manage.py migrate
if errorlevel 1 (pause & exit /b 1)
echo First use? After this run, open another terminal and run: python manage.py setup_manager
python manage.py runserver 127.0.0.1:8000
pause
