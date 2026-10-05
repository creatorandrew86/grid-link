@echo off
cd /d "%~dp0.."
.tools\venv\Scripts\python.exe demo\prepare_demo.py --seed
