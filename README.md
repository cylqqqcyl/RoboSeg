# Robot Data Segmentation Agent

A Minimum Viable Product (MVP) for analyzing robotic dashcam videos and segmenting them into timestamped action segments.

## Project Structure

- `backend/`: Python FastAPI backend
- `frontend/`: React.js frontend (coming soon)

## Features

- Upload robot dashcam videos
- AI-powered video analysis using Google Gemini API
- Display timestamped action segments
- Asynchronous video processing with Celery and Redis

## Getting Started

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # Linux/Mac
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your Gemini API key:
   
   Create a `.env` file in the backend directory with the following content:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/1
   ```
   
   You can obtain a Gemini API key by:
   - Go to https://aistudio.google.com/app/apikey
   - Sign in with your Google account
   - Create a new API key
   - Copy the key to your `.env` file

5. Install and run Redis (required for Celery):

   **Using Docker (recommended):**
   ```
   docker run -d -p 6379:6379 --name redis-roboseg redis
   ```

   **On Windows without Docker:**
   Download and install Redis from https://github.com/microsoftarchive/redis/releases

   **On Linux:**
   ```
   sudo apt update
   sudo apt install redis-server
   sudo systemctl start redis-server
   ```

6. Start the Celery worker (in a separate terminal window):
   ```
   # Make sure you're in the backend directory with virtual environment activated
   celery -A celery_app worker --loglevel=info
   ```

7. Run the API server (in another terminal window):
   ```
   # Make sure you're in the backend directory with virtual environment activated
   python main.py
   ```

8. Access the API documentation at: http://localhost:8000/docs

### API Endpoints

- `GET /health`: Check if the API is running
- `POST /upload_video/`: Upload a video file for analysis
  - Returns a task_id for tracking the processing status
  - Example response:
    ```json
    {
      "task_id": "7e9f8a23-4b9d-4c80-9e1f-8b5c7a2e8d3f",
      "message": "Video processing task started"
    }
    ```

- `GET /tasks/{task_id}/status`: Check the status of a video processing task
  - Returns the current status (PENDING, STARTED, SUCCESS, FAILURE)
  - Example response:
    ```json
    {
      "task_id": "7e9f8a23-4b9d-4c80-9e1f-8b5c7a2e8d3f",
      "status": "SUCCESS"
    }
    ```

- `GET /tasks/{task_id}/result`: Get the result of a completed task
  - Returns the segmentation result if the task is complete
  - Example response:
    ```json
    {
      "task_id": "7e9f8a23-4b9d-4c80-9e1f-8b5c7a2e8d3f",
      "status": "SUCCESS",
      "result": {
        "segments": [
          {
            "start_time": "00:12",
            "end_time": "00:58",
            "description": "Robot picks up item from table"
          },
          {
            "start_time": "00:59",
            "end_time": "01:45",
            "description": "Robot moves to destination"
          }
        ]
      }
    }
    ```

- `DELETE /tasks/{task_id}/cleanup`: Clean up video files after processing
  - Deletes the video file associated with a task
  - Example response:
    ```json
    {
      "message": "Cleaned up file for task 7e9f8a23-4b9d-4c80-9e1f-8b5c7a2e8d3f"
    }
    ```
