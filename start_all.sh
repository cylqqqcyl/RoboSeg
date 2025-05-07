#!/bin/bash
echo "Starting RoboSeg Application"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if something is already using port 6379
if nc -z localhost 6379 &>/dev/null; then
    echo "Port 6379 is already in use. Redis might be already running."
    echo "Checking if it's our Redis container..."
    if docker ps | grep -q roboseg-redis; then
        echo "Redis container is already running."
    else
        echo "Another service is using port 6379. Please stop it before running this script."
        echo "If you're sure Redis is already running, you can continue."
    fi
else
    # Start Redis container
    echo "Starting Redis Docker container..."
    docker run --name roboseg-redis -p 6379:6379 -d redis
    if [ $? -ne 0 ]; then
        echo "Checking if Redis container already exists..."
        if [ "$(docker ps -a -q -f name=roboseg-redis)" ]; then
            echo "Starting existing Redis container..."
            docker start roboseg-redis
        else
            echo "Failed to start Redis container."
            exit 1
        fi
    fi
fi

# Setup virtual environment for backend
echo "Setting up backend environment..."
pushd backend > /dev/null
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt
echo "Installing missing packages..."
pip install grpcio protobuf

# Start Celery worker - fix module path
echo "Starting Celery worker..."
PYTHONIOENCODING=utf-8 celery -A celery_app worker --loglevel=info > celery_output.log 2>&1 &
CELERY_PID=$!

# Start FastAPI server
echo "Starting FastAPI server..."
PYTHONIOENCODING=utf-8 python main.py > api_output.log 2>&1 &
API_PID=$!
popd > /dev/null

# Start Frontend with proper encoding
echo "Starting Frontend..."
pushd frontend > /dev/null
LANG=en_US.UTF-8 npm run dev > ../frontend_output.log 2>&1 &
FRONTEND_PID=$!
popd > /dev/null

echo "All services started!"
echo "Frontend available at: http://localhost:5173"
echo "Backend API available at: http://localhost:8000/docs"
echo ""
echo "Service outputs are being logged to:"
echo "- backend/celery_output.log"
echo "- backend/api_output.log"
echo "- frontend_output.log"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle graceful shutdown
function cleanup {
    echo "Stopping services..."
    kill $FRONTEND_PID
    kill $API_PID
    kill $CELERY_PID
    
    # Only stop Redis if we started it
    if [ ! "$(nc -z localhost 6379 &>/dev/null && docker ps | grep -q roboseg-redis)" ]; then
        docker stop roboseg-redis
    fi
    echo "All services stopped."
    exit 0
}

trap cleanup SIGINT

# Display logs in real-time (tail the log files)
tail -f backend/celery_output.log backend/api_output.log frontend_output.log 