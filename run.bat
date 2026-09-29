@echo off
call venv\Scripts\activate.bat
set PYTHONPATH=%~dp0deps\hailo-apps
set HAILO_ARCH=hailo8
python src\meal_monitoring.py -n yolov8m -i usb --show-fps %*
