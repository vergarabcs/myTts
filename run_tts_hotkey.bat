@echo off
REM Activate the virtual environment
call %~dp0.venv\Scripts\activate.bat

REM Run the TTS hotkey script
python tts_hotkey.py

REM Deactivate the virtual environment (optional, as the script ends)
REM deactivate