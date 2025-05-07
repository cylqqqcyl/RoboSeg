from fastapi import FastAPI, UploadFile, File, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import Dict, Any
import config
import os
import tempfile
import json
import time
import shutil
import uuid
from celery.result import AsyncResult

# Import models from models.py
from models import ActionSegment, SegmentationResponse, TaskResponse, TaskStatusResponse, TaskResultResponse, VideoURLRequest
# Import Celery task
from tasks import process_video_for_segmentation
# Import Celery application
from celery_app import celery_app

app = FastAPI(title="Robot Data Segmentation Agent")

# Add CORS middleware to allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the uploads directory for static file serving
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}

@app.post("/upload_video/", response_model=TaskResponse)
async def upload_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload a video file and queue it for asynchronous processing with Gemini API.
    
    The endpoint immediately returns a task_id that can be used to check the status
    and retrieve results later.
    """
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    # Check file type
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    try:
        # Generate unique task ID and filename
        task_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{task_id}{file_extension}"
        file_path = os.path.join(config.UPLOAD_DIR, unique_filename)
        
        # Save uploaded file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Queue the Celery task for processing
        # Store Celery task ID in a file for debugging and cross-referencing
        celery_task = process_video_for_segmentation.delay(task_id=task_id, video_path=file_path)
        celery_task_id = celery_task.id
        
        # Store mapping between our task_id and celery's task_id
        print(f"Created task mapping: App task_id={task_id} -> Celery task_id={celery_task_id}")
        
        # Create a task ID mapping file for debugging
        mapping_path = os.path.join(config.UPLOAD_DIR, f"{task_id}.task_info")
        with open(mapping_path, "w") as f:
            f.write(json.dumps({
                "app_task_id": task_id,
                "celery_task_id": celery_task_id,
                "file_path": file_path,
                "created_at": time.time()
            }))
        
        return {
            "task_id": task_id,
            "message": "Video processing task started"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error starting video processing task: {str(e)}"
        )

@app.post("/process_video_from_url/", response_model=TaskResponse)
async def process_video_from_url(request: VideoURLRequest) -> Dict[str, Any]:
    """
    Process a video from the provided URL using Gemini API.
    
    The endpoint immediately returns a task_id that can be used to check the status
    and retrieve results later.
    """
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Queue the Celery task for processing
        celery_task = process_video_for_segmentation.delay(task_id=task_id, video_url=str(request.video_url))
        celery_task_id = celery_task.id
        
        # Store mapping between our task_id and celery's task_id
        print(f"Created URL task mapping: App task_id={task_id} -> Celery task_id={celery_task_id}")
        
        # Create a task ID mapping file for debugging
        mapping_path = os.path.join(config.UPLOAD_DIR, f"{task_id}.task_info")
        with open(mapping_path, "w") as f:
            f.write(json.dumps({
                "app_task_id": task_id,
                "celery_task_id": celery_task_id,
                "video_url": str(request.video_url),
                "created_at": time.time()
            }))
        
        return {
            "task_id": task_id,
            "message": "Video URL processing task started"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error starting video URL processing task: {str(e)}"
        )

@app.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str = Path(..., description="ID of the task to check")) -> Dict[str, Any]:
    """
    Check the status of a video processing task.
    
    Returns the current status of the task: PENDING, STARTED, SUCCESS, FAILURE, etc.
    """
    try:
        # Check if we have a task mapping file to get the Celery task ID
        celery_task_id = None
        mapping_path = os.path.join(config.UPLOAD_DIR, f"{task_id}.task_info")
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, "r") as f:
                    mapping_data = json.loads(f.read())
                    celery_task_id = mapping_data.get("celery_task_id")
                    print(f"Found task mapping file: {task_id} -> {celery_task_id}")
            except Exception as e:
                print(f"Error reading task mapping file: {str(e)}")
        
        # First try with the original task ID
        task_result = AsyncResult(task_id, app=celery_app)
        
        # If we have a celery task ID and the original task ID doesn't have a valid state,
        # try with the Celery task ID
        if celery_task_id and task_result.state == 'PENDING':
            print(f"Trying with Celery task ID: {celery_task_id}")
            celery_task_result = AsyncResult(celery_task_id, app=celery_app)
            if celery_task_result.state != 'PENDING':
                print(f"Using Celery task result with state: {celery_task_result.state}")
                task_result = celery_task_result
        
        # Get the current state (no refresh method available in AsyncResult)
        current_state = task_result.state
        print(f"Task {task_id} current state: {current_state}")
        
        # Check if task exists in backend (only if backend has exists method)
        if task_result.backend and hasattr(task_result.backend, 'exists') and not task_result.backend.exists(task_result.id):
            print(f"Task {task_id} not found in result backend")
            
        # If pending for too long, check if the task is actually completed
        if current_state == 'PENDING':
            # Check if we can get a result anyway (some tasks complete but don't update status)
            try:
                result = task_result.get(timeout=0.1)  # Very short timeout to just check if result exists
                if result:
                    print(f"Task {task_id} has result despite PENDING status: {result}")
                    current_state = 'SUCCESS'  # Override the state if we have a result
            except Exception as e:
                print(f"Attempted to get result for PENDING task {task_id}: {str(e)}")
        
        return {
            "task_id": task_id,
            "status": current_state
        }
    
    except Exception as e:
        import traceback
        print(f"Error in get_task_status: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving task status: {str(e)}"
        )

@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str = Path(..., description="ID of the task to retrieve result for")) -> Dict[str, Any]:
    """
    Retrieve the result of a completed video processing task.
    
    If the task is still in progress, returns the current status.
    If the task is complete, returns the segmentation result.
    If the task failed, returns error information.
    """
    try:
        # Check if we have a task mapping file to get the Celery task ID
        celery_task_id = None
        mapping_path = os.path.join(config.UPLOAD_DIR, f"{task_id}.task_info")
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, "r") as f:
                    mapping_data = json.loads(f.read())
                    celery_task_id = mapping_data.get("celery_task_id")
                    print(f"Found task mapping file for result: {task_id} -> {celery_task_id}")
            except Exception as e:
                print(f"Error reading task mapping file for result: {str(e)}")
        
        # First try with the original task ID
        task_result = AsyncResult(task_id, app=celery_app)
        
        # If we have a celery task ID and the original task ID doesn't show results,
        # try with the Celery task ID
        if celery_task_id and task_result.state == 'PENDING':
            print(f"Trying result with Celery task ID: {celery_task_id}")
            celery_task_result = AsyncResult(celery_task_id, app=celery_app)
            if celery_task_result.state != 'PENDING':
                print(f"Using Celery task result with state: {celery_task_result.state}")
                task_result = celery_task_result
        
        # Get the current state (no refresh method available in AsyncResult)
        current_state = task_result.state
        print(f"Getting result for task {task_id}, current state: {current_state}")
        
        # Try to get result even if state says PENDING (could be a state reporting issue)
        try:
            if current_state == 'PENDING':
                # Check if task has been running for a while (in case it's done but status not updated)
                mapping_file_time = 0
                try:
                    if os.path.exists(mapping_path):
                        with open(mapping_path, "r") as f:
                            mapping_data = json.loads(f.read())
                            created_at = mapping_data.get("created_at", 0)
                            task_age = time.time() - created_at
                            print(f"Task age: {task_age} seconds")
                            
                            # If task is older than 20 seconds and still PENDING, try to get result
                            if task_age > 20:
                                print(f"Task is older than 20 seconds, attempting to force result retrieval")
                                try:
                                    result = task_result.get(timeout=0.5)
                                    if result:
                                        print(f"Found result for aged task {task_id} despite PENDING status")
                                        current_state = 'SUCCESS'
                                except Exception as e:
                                    print(f"No result available for aged PENDING task {task_id}: {str(e)}")
                except Exception as e:
                    print(f"Error checking task age: {str(e)}")
                
                # Try to get result with a short timeout as a final check
                if current_state == 'PENDING':
                    try:
                        result = task_result.get(timeout=0.5)
                        if result:
                            print(f"Found result for task {task_id} despite PENDING status")
                            current_state = 'SUCCESS'
                    except Exception as e:
                        print(f"No result available for PENDING task {task_id}: {str(e)}")
                        # Keep the PENDING state
            
            # Handle based on current state (which might have been updated)    
            if current_state == 'SUCCESS':
                # For SUCCESS state, we can safely try to get the result
                result = task_result.get()
                
                # Check if result contains error
                if isinstance(result, dict) and 'error' in result:
                    return {
                        "task_id": task_id,
                        "status": "FAILURE",
                        "error": result['error']
                    }
                
                return {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "result": result
                }
            
            elif current_state == 'FAILURE':
                return {
                    "task_id": task_id,
                    "status": "FAILURE",
                    "error": str(task_result.info)
                }
            
            else:
                return {
                    "task_id": task_id,
                    "status": current_state
                }
                
        except Exception as result_e:
            print(f"Error retrieving result for task {task_id}: {str(result_e)}")
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": f"Error retrieving result: {str(result_e)}"
            }
    
    except Exception as e:
        import traceback
        print(f"Error in get_task_result: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving task result: {str(e)}"
        )

# Cleanup endpoint (optional) to manually delete processed videos
@app.delete("/tasks/{task_id}/cleanup")
async def cleanup_task(task_id: str = Path(..., description="ID of the task to clean up")) -> Dict[str, Any]:
    """
    Delete the video file associated with a task.
    
    This endpoint is useful for manual cleanup when automatic cleanup fails
    or for freeing storage space after debugging.
    """
    try:
        # Find all potential file paths with this task ID
        for filename in os.listdir(config.UPLOAD_DIR):
            if filename.startswith(task_id):
                file_path = os.path.join(config.UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return {"message": f"Cleaned up file for task {task_id}"}
        
        return {"message": f"No files found for task {task_id}"}
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error cleaning up task files: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=config.API_HOST, 
        port=config.API_PORT, 
        reload=config.DEBUG
    ) 