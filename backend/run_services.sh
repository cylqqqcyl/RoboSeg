#!/bin/bash
echo "Starting Robot Segmentation Agent Services"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Check Redis
echo "Checking Redis..."
redis-cli ping > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Redis not running. Please start Redis first with:"
    echo "sudo systemctl start redis-server  # For Linux"
    echo "brew services start redis          # For macOS with Homebrew"
    exit 1
fi

# Start Celery worker (background)
echo "Starting Celery worker..."
celery -A backend.celery_app worker --loglevel=info &
CELERY_PID=$!

# Start FastAPI server (foreground)
echo "Starting FastAPI server..."
python main.py

# Clean up Celery worker when FastAPI server stops
kill $CELERY_PID

echo "Services stopped" 