import os
import json
import asyncio
import requests
from typing import Dict, Any, Optional
import mimetypes  # For guessing MIME types if needed for other URLs before download
import re         # For YouTube URL detection

# Updated imports for Google Gen AI SDK
from google import genai
from google.genai import types # For types.GenerateContentConfig, types.FileState, etc.
from google.genai import errors as genai_errors # For specific API error handling
from google.genai.types import GenerateContentConfig, Content, Part, FileData
from google.genai.types import File as GenAIFile          

from celery_app import celery_app # Assuming these are your local modules
import config
from models import ActionSegment, SegmentationResponse


def is_youtube_url(url):
    if not url:
        return False
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    return re.match(youtube_regex, url)


async def _process_video_async(
    task_id: str,
    video_path: Optional[str] = None,
    video_url: Optional[str] = None
) -> Dict[str, Any]:
    client: Optional[genai.Client] = None
    downloaded_file_path: Optional[str] = None
    api_response_text: Optional[str] = None
    file_deleted_in_exception_block = False
    video_model_input: Optional[genai.files.File | types.Part] = None
    gemini_file_name_for_cleanup: Optional[str] = None

    try:
        if not config.GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not configured."}
        
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        if video_url and is_youtube_url(video_url):
            print(f"Processing as direct YouTube URL: {video_url}")
            try:
                video_model_input = types.Part(
                    file_data=types.FileData(file_uri=video_url)
                )
                print(f"Successfully created Part for YouTube URL: {video_url}")
            except Exception as e:
                return {"error": f"Failed to create Part from YouTube URL '{video_url}': {str(e)}"}

        elif video_path or video_url:
            current_file_path = video_path

            if video_url and not current_file_path:
                print(f"Downloading video from general URL: {video_url}")
                try:
                    file_extension = os.path.splitext(video_url.split('?')[0])[-1] or '.mp4'
                    if not file_extension.startswith('.'):
                        file_extension = '.' + file_extension
                    file_name = f"{task_id}{file_extension}"

                    upload_dir = getattr(config, 'UPLOAD_DIR', 'uploads')
                    if not os.path.exists(upload_dir):
                        os.makedirs(upload_dir, exist_ok=True)
                    downloaded_file_path = os.path.join(upload_dir, file_name)

                    response = requests.get(video_url, stream=True, timeout=60)
                    response.raise_for_status()
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('video/'):
                        if os.path.exists(downloaded_file_path): os.remove(downloaded_file_path)
                        raise ValueError(f"URL does not point to a video file. Content-Type: {content_type}")
                    with open(downloaded_file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    current_file_path = downloaded_file_path
                    print(f"Video downloaded successfully to {current_file_path}")
                except requests.RequestException as e:
                    return {"error": f"Failed to download video from URL: {str(e)}"}
                except ValueError as e:
                    return {"error": str(e)}
                except Exception as e:
                    if 'downloaded_file_path' in locals() and os.path.exists(downloaded_file_path):
                        try:
                            os.remove(downloaded_file_path)
                        except OSError: pass
                    return {"error": f"Error processing video URL for download: {str(e)}"}

            if not current_file_path:
                return {"error": "Video source (file path or URL) not available or failed to prepare."}
            if not os.path.exists(current_file_path):
                return {"error": f"Video file not found at {current_file_path}"}

            print(f"Uploading file to Gemini File API: {current_file_path}")
            try:
                uploaded_file_response = await client.aio.files.upload(file=current_file_path)
                gemini_file_name_for_cleanup = uploaded_file_response.name

                file_for_model = uploaded_file_response
                max_retries = 30 
                retry_delay_seconds = 20
                retry_count = 0

                while file_for_model.state != types.FileState.ACTIVE and retry_count < max_retries:
                    current_state_obj = file_for_model.state
                    current_state_name = ""
                    current_state_value_for_log = ""

                    if isinstance(current_state_obj, int):
                        try:
                            current_state_name = types.FileState(current_state_obj).name
                            current_state_value_for_log = current_state_obj
                        except ValueError:
                            current_state_name = f"UNKNOWN_INT_STATE_{current_state_obj}"
                            current_state_value_for_log = current_state_obj
                    elif hasattr(current_state_obj, 'name'):
                        current_state_name = current_state_obj.name
                        current_state_value_for_log = current_state_obj.value if hasattr(current_state_obj, 'value') else str(current_state_obj)
                    else:
                        current_state_name = str(current_state_obj)
                        current_state_value_for_log = str(current_state_obj)

                    print(f"File not active, current state: {current_state_name} ({current_state_value_for_log}). Retrying {retry_count+1}/{max_retries} in {retry_delay_seconds}s...")
                    await asyncio.sleep(retry_delay_seconds)
                    file_for_model = await client.aio.files.get(name=gemini_file_name_for_cleanup)
                    retry_count += 1
                    print(f"Polled file details (Try {retry_count}): {file_for_model}")
                    if hasattr(file_for_model, 'error') and file_for_model.error:
                        print(f"!!! File processing error reported by API (Try {retry_count}): {file_for_model.error}")

                if file_for_model.state != types.FileState.ACTIVE:
                    current_state_obj_final = file_for_model.state
                    current_state_name_final = types.FileState(current_state_obj_final).name if isinstance(current_state_obj_final, int) else (current_state_obj_final.name if hasattr(current_state_obj_final, 'name') else str(current_state_obj_final))
                    current_state_value_final = current_state_obj_final.value if hasattr(current_state_obj_final, 'value') else current_state_obj_final

                    file_error_details = ""
                    if hasattr(file_for_model, 'error') and file_for_model.error:
                        file_error_details = f" Reported API Error: {file_for_model.error}"

                    if client and gemini_file_name_for_cleanup:
                        try:
                            await client.aio.files.delete(name=gemini_file_name_for_cleanup)
                            print(f"Cleaned up Gemini file {gemini_file_name_for_cleanup} due to non-ACTIVE state.")
                            file_deleted_in_exception_block = True
                        except Exception as del_e:
                            print(f"Warning: Failed to delete Gemini file {gemini_file_name_for_cleanup} after non-ACTIVE state: {str(del_e)}")
                    return {"error": f"File upload to Gemini failed to become ACTIVE. Final state: {current_state_obj_final}{file_error_details}"}

                active_state_name = file_for_model.state.name if hasattr(file_for_model.state, 'name') else types.FileState(file_for_model.state).name
                print(f"File is ACTIVE ({active_state_name}) on Gemini. Proceeding with content generation.")
                print(f"Active file details: URI='{file_for_model.uri}', MimeType='{file_for_model.mime_type}'")

                video_model_input = file_for_model

            except Exception as e:
                if client and gemini_file_name_for_cleanup and not file_deleted_in_exception_block:
                    try:
                        await client.aio.files.delete(name=gemini_file_name_for_cleanup)
                        print(f"Cleaned up Gemini file {gemini_file_name_for_cleanup} due to an exception during upload/polling.")
                        file_deleted_in_exception_block = True
                    except Exception as del_e:
                        print(f"Warning: Failed to delete Gemini file {gemini_file_name_for_cleanup} after exception: {str(del_e)}")
                return {"error": f"Failed during File API processing for '{current_file_path}': {str(e)}"}
        else:
            return {"error": "Video source (file path or URL) not provided."}

        if not video_model_input:
            return {"error": "Video input for the model could not be prepared."}

        prompt = """You are an expert in analyzing robotic task videos. Your objective is to extract key, discrete actions performed by the robot(s) and their corresponding start and end timestamps from the provided video. The video may incorporate views from multiple cameras, including stationary and robot wrist-mounted cameras, showing robotic manipulation tasks.

        Focus on tangible, goal-oriented actions performed by the robot(s), such as picking up objects, placing objects, manipulating tools, moving to specific locations, or interacting with its environment. Avoid describing continuous background activity or minute, inconsequential movements unless they are part of a larger, nameable action.

        Provide the output as a single JSON object adhering strictly to the following schema:
        {
        "action_segments": [
            {
            "action": "Concise description of the robot's action (e.g., 'robot gripper picks up red block', 'robot arm moves to a blue container', 'robot tightens screw with tool')",
            "start_time": "HH:MM:SS.mmm (timestamp of action start, e.g., 00:01:12.345)",
            "end_time": "HH:MM:SS.mmm (timestamp of action end, e.g., 00:01:15.678)"
            }
        ]
        }

        Key Instructions:
        - Analyze the entire video provided.
        - Timestamps must be precise and strictly follow the "HH:MM:SS.mmm" format.
        - Each segment should represent a distinct, continuous action performed by a robot.
        - Descriptions should be in active voice from the robot's perspective where appropriate (e.g., "robot picks up" rather than "red block is picked up").
        - If multiple distinct robotic actions occur sequentially or in parallel (if discernible as separate tasks), list each as a separate segment.

        Example (Illustrative, adapt to robotic context):
        Input: A video of a robot arm assembling parts.
        Output:
        {
        "action_segments": [
            {
            "action": "robot arm approaches and grasps gear A",
            "start_time": "00:00:05.250",
            "end_time": "00:00:08.100"
            },
            {
            "action": "robot arm moves gear A towards assembly point",
            "start_time": "00:00:08.500",
            "end_time": "00:00:12.750"
            },
            {
            "action": "robot arm inserts gear A into slot B",
            "start_time": "00:00:13.000",
            "end_time": "00:00:15.200"
            }
        ]
        }"""
        response_schema_for_config = {
            "type": "object",
            "properties": {
                "action_segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action":      {"type": "string"},
                            "start_time":  {"type": "string"},
                            "end_time":    {"type": "string"}
                        },
                        "required": ["action", "start_time", "end_time"]
                    }
                }
            },
            "required": ["action_segments"]
        }


        model_name = getattr(config, 'GEMINI_MODEL_NAME', 'gemini-2.0-flash')
        
        print(f"Generating content with model: {model_name}")
        # 1. Build the video Part (works for both File API uploads and YouTube URLs)
        if isinstance(video_model_input, GenAIFile):
            video_part = Part.from_uri(
                file_uri=video_model_input.uri,
                mime_type=video_model_input.mime_type
            )
        elif isinstance(video_model_input, Part):
            video_part = video_model_input            # YouTube branch already gave us a Part
        else:
            return {"error": "Unsupported video_model_input type."}

        # 2. One Content that holds BOTH video + prompt
        user_message = Content(
            parts=[
                video_part,                            # put the video first
                Part(text=prompt)                      # then the instructions
            ]
        )

        # 3. Generation config (newer class name)
        gen_cfg = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema_for_config
        )

        # 4. Call the model
        api_response = await client.aio.models.generate_content(
            model=model_name,
            contents=[user_message],                  # list with ONE valid Content
            config=gen_cfg                 # ← use generation_config
        )
        print("Content generation complete. Response received from Gemini.")
        
        if not api_response.candidates:
            return {"error": "Gemini response had no candidates."}
        
        try:
            api_response_text = api_response.text
        except ValueError:
            finish_reason_val = "UNKNOWN"
            if api_response.candidates and hasattr(api_response.candidates[0], 'finish_reason'):
                 finish_reason_val = api_response.candidates[0].finish_reason.name if hasattr(api_response.candidates[0].finish_reason, 'name') else str(api_response.candidates[0].finish_reason)

            safety_ratings_val = "UNKNOWN"
            if api_response.candidates and hasattr(api_response.candidates[0], 'safety_ratings') and api_response.candidates[0].safety_ratings:
                safety_ratings_val = str(api_response.candidates[0].safety_ratings)
            
            print(f"Gemini API response was blocked or did not return text. Finish Reason: {finish_reason_val}")
            print(f"Safety Ratings: {safety_ratings_val}")
            prompt_feedback = api_response.prompt_feedback if hasattr(api_response, 'prompt_feedback') else "N/A"
            print(f"Prompt Feedback: {prompt_feedback}")

            return {"error": f"Gemini API response was blocked or did not return text. Finish Reason: {finish_reason_val}"}

        print(f"Gemini response text: {api_response_text}")
        result_json = json.loads(api_response_text)
        validated_result = SegmentationResponse(**result_json).model_dump()

        # Add downloaded_file_path to the result if available
        if 'downloaded_file_path' in locals() and downloaded_file_path and os.path.exists(downloaded_file_path):
            # Add the file path relative to the server root for serving
            file_name = os.path.basename(downloaded_file_path)
            validated_result["downloaded_video_path"] = f"uploads/{file_name}"

        return validated_result
        
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {str(e)}. Response text was: '{api_response_text if api_response_text is not None else 'N/A'}'")
        return {"error": f"Failed to parse Gemini response as JSON: {str(e)}"}
    except genai_errors.APIError as e:
        import traceback
        print(f"A GenAI API error occurred: {str(e)}\n{traceback.format_exc()}")
        if client and gemini_file_name_for_cleanup and not file_deleted_in_exception_block:
            try:
                await client.aio.files.delete(name=gemini_file_name_for_cleanup)
                print(f"Cleaned up Gemini file {gemini_file_name_for_cleanup} due to API exception.")
                file_deleted_in_exception_block = True
            except Exception as del_e:
                print(f"Warning: Failed to delete Gemini file {gemini_file_name_for_cleanup} after API exception: {str(del_e)}")
        return {"error": f"Error processing video (API Error): {str(e)}"}
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {str(e)}\n{traceback.format_exc()}")
        if client and gemini_file_name_for_cleanup and not file_deleted_in_exception_block:
            try:
                await client.aio.files.delete(name=gemini_file_name_for_cleanup)
                print(f"Cleaned up Gemini file {gemini_file_name_for_cleanup} due to unexpected exception.")
                file_deleted_in_exception_block = True
            except Exception as del_e:
                print(f"Warning: Failed to delete Gemini file {gemini_file_name_for_cleanup} after unexpected exception: {str(del_e)}")
        return {"error": f"Error processing video: {str(e)}"}
    finally:
        if client and gemini_file_name_for_cleanup and not file_deleted_in_exception_block:
            try:
                print(f"Attempting to delete Gemini file in finally block: {gemini_file_name_for_cleanup}")
                await client.aio.files.delete(name=gemini_file_name_for_cleanup)
                print(f"Successfully deleted Gemini file: {gemini_file_name_for_cleanup} in finally block.")
            except genai_errors.NotFoundError:
                print(f"Gemini file {gemini_file_name_for_cleanup} not found in finally block (already deleted or never fully created).")
            except genai_errors.PermissionDeniedError:
                print(f"Permission denied attempting to delete Gemini file {gemini_file_name_for_cleanup} in finally block. It might have been deleted by another process or retained due to ongoing operations.")
            except Exception as e:
                print(f"Warning: Failed to delete Gemini file in finally block '{gemini_file_name_for_cleanup}': {type(e).__name__} - {str(e)}")
        
        # Clean up downloaded local file
        if 'downloaded_file_path' in locals() and downloaded_file_path and os.path.exists(downloaded_file_path):
            # Don't delete downloaded files from URLs as they're needed for display
            # We'll let a separate cleanup task handle this later if needed
            pass
        
        # Clean up uploaded video file if it exists
        if 'video_path' in locals() and video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                print(f"Successfully deleted uploaded video file: {video_path}")
            except Exception as e:
                print(f"Warning: Failed to delete uploaded video file '{video_path}': {str(e)}")


@celery_app.task(bind=True, name='tasks.process_video_for_segmentation')
def process_video_for_segmentation(
    self,
    task_id: str,
    video_path: Optional[str] = None,
    video_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Celery task that processes a video for segmentation using Google's Gemini API.
    This is a synchronous wrapper around the async implementation.
    """
    return asyncio.run(_process_video_async(task_id, video_path, video_url))