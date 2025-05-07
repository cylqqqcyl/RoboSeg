from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Optional

class ActionSegment(BaseModel):
    """Model for a single action segment with start and end times"""
    start_time: str = Field(..., description="Start time of the segment in MM:SS format")
    end_time: str = Field(..., description="End time of the segment in MM:SS format")
    action: str = Field(..., description="Description of the robot action")

class SegmentationResponse(BaseModel):
    """Response model containing a list of action segments"""
    action_segments: List[ActionSegment] = Field(alias="action_segments")
    downloaded_video_path: Optional[str] = None

class TaskResponse(BaseModel):
    """Response model for task creation"""
    task_id: str
    message: str

class TaskStatusResponse(BaseModel):
    """Response model for task status"""
    task_id: str
    status: str

class TaskResultResponse(BaseModel):
    """Response model for task result"""
    task_id: str
    status: str
    result: Optional[SegmentationResponse] = None
    error: Optional[str] = None

class VideoURLRequest(BaseModel):
    """Request model for video URL processing"""
    video_url: HttpUrl = Field(..., description="URL of the video to process") 