@echo off
echo Starting Robot Segmentation Agent Services

REM Check if venv exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Start Redis if it's not already running (assuming it's installed)
echo Checking Redis...
REM Add your Redis check/start command here if you have a local Redis installation

REM Start Celery worker
echo Starting Celery worker...
start cmd /k "venv\Scripts\activate && celery -A backend.celery_app worker --loglevel=info"

REM Start FastAPI server
echo Starting FastAPI server...
start cmd /k "venv\Scripts\activate && python main.py"

echo All services started! API available at http://localhost:8000/docs 