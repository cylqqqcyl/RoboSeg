import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import VideoUpload from './components/VideoUpload'
import TaskStatus from './components/TaskStatus'
import './App.css'

function App() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [videoURL, setVideoURL] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [status, setStatus] = useState(null)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [isPolling, setIsPolling] = useState(false)
  const [inputType, setInputType] = useState(null) // 'file' or 'url'
  const videoPlayerRef = useRef(null)

  const handleUpload = async (file) => {
    setSelectedFile(file)
    setVideoURL(URL.createObjectURL(file))
    setError(null)
    setStatus('Uploading...')
    setResults(null)
    setInputType('file')
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await axios.post('http://localhost:8000/upload_video/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      
      setTaskId(response.data.task_id)
      setStatus('Processing...')
      setIsPolling(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload video')
      setStatus('FAILURE')
    }
  }

  const handleUrlUpload = async (url) => {
    setVideoURL(null) // No preview for URL uploads
    setSelectedFile(null)
    setError(null)
    setStatus('Processing URL...')
    setResults(null)
    setInputType('url')
    
    try {
      const response = await axios.post('http://localhost:8000/process_video_from_url/', {
        video_url: url
      }, {
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      setTaskId(response.data.task_id)
      setStatus('Processing...')
      setIsPolling(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process video URL')
      setStatus('FAILURE')
    }
  }

  const handleSegmentClick = (startTime) => {
    if (videoPlayerRef.current) {
      // Convert time string to seconds if it's not already in seconds
      let timeInSeconds = startTime;
      
      if (typeof startTime === 'string' && startTime.includes(':')) {
        const [minutes, seconds] = startTime.split(':').map(Number);
        timeInSeconds = minutes * 60 + seconds;
      }
      
      videoPlayerRef.current.currentTime = timeInSeconds;
      videoPlayerRef.current.play();
    }
  }

  useEffect(() => {
    let interval = null
    
    if (isPolling && taskId) {
      interval = setInterval(async () => {
        try {
          const statusResponse = await axios.get(`http://localhost:8000/tasks/${taskId}/status`)
          const currentStatus = statusResponse.data.status
          
          setStatus(currentStatus)
          
          if (currentStatus === 'SUCCESS') {
            setIsPolling(false)
            const resultResponse = await axios.get(`http://localhost:8000/tasks/${taskId}/result`)
            setResults(resultResponse.data.result.action_segments)
            
            // Check if there's a downloaded video path and set it
            if (resultResponse.data.result.downloaded_video_path) {
              setVideoURL(`http://localhost:8000/${resultResponse.data.result.downloaded_video_path}`)
            }
          } else if (currentStatus === 'FAILURE') {
            setIsPolling(false)
            const resultResponse = await axios.get(`http://localhost:8000/tasks/${taskId}/result`)
            setError(resultResponse.data.error || 'Task failed. Please try again.')
          }
        } catch (err) {
          setIsPolling(false)
          setError(err.response?.data?.detail || 'Failed to check task status')
          setStatus('FAILURE')
        }
      }, 1000) // Poll every 1 second
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [taskId, isPolling])

  return (
    <div className="app-container">
      <header>
        <h1>Robot Data<br></br> Segmentation Agent</h1>
      </header>
      
      <main>
        <section className="upload-section">
          <VideoUpload 
            onUpload={handleUpload}
            onUrlUpload={handleUrlUpload}
          />
        </section>
        
        {videoURL && (
          <section className="video-preview">
            <h2>Video Preview</h2>
            <video 
              ref={videoPlayerRef}
              src={videoURL} 
              controls 
              width="100%" 
              height="auto"
            />
          </section>
        )}
        
        {!videoURL && inputType === 'url' && status && (
          <section className="url-info">
            <h2>URL Video Processing</h2>
            <p>Processing video from URL. Preview will appear when available.</p>
          </section>
        )}
        
        {(taskId || status || results || error) && (
          <section className="status-section">
            <TaskStatus 
              taskId={taskId}
              status={status}
              results={results}
              error={error}
              onSegmentClick={handleSegmentClick}
            />
          </section>
        )}
      </main>
    </div>
  )
}

export default App
