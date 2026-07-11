@echo off
setlocal

set "ROOT=%~dp0.."
set "INPUT=%ROOT%\data\raw\ostrich_shaky.mp4"
if not defined OUTPUT set "OUTPUT=%ROOT%\results\cpu_baseline\ostrich_stabilized_r45_crop80_reflect.mp4"
if not defined METRICS set "METRICS=%ROOT%\results\cpu_baseline\ostrich_metrics_r45_crop80_reflect.csv"
if not defined SMOOTHING_RADIUS set "SMOOTHING_RADIUS=45"
if not defined CROP_RATIO set "CROP_RATIO=0.80"

if exist "%ROOT%\.venv312\Scripts\python.exe" (
    set "PYTHON=%ROOT%\.venv312\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" "%ROOT%\src\cpu_stabilize.py" --input "%INPUT%" --output "%OUTPUT%" --metrics "%METRICS%" --smoothing-radius "%SMOOTHING_RADIUS%" --crop-ratio "%CROP_RATIO%"

endlocal
