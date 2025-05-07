import React, { useState } from 'react';

function VideoUpload({ onUpload, onUrlUpload }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [uploadType, setUploadType] = useState('file'); // 'file' or 'url'

  const handleFileChange = (event) => {
    if (event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
      setVideoUrl('');
      setUploadType('file');
    }
  };

  const handleUrlChange = (event) => {
    setVideoUrl(event.target.value);
    if (event.target.value) {
      setSelectedFile(null);
      setUploadType('url');
    }
  };

  const handleUpload = () => {
    if (uploadType === 'file' && selectedFile) {
      onUpload(selectedFile);
    } else if (uploadType === 'url' && videoUrl) {
      onUrlUpload(videoUrl);
    }
  };

  const isUploadDisabled = (uploadType === 'file' && !selectedFile) || 
                           (uploadType === 'url' && !videoUrl);

  return (
    <div className="upload-container">
      <h2>Upload Video</h2>
      <div className="upload-form">
        <input 
          type="file" 
          accept="video/*"
          onChange={handleFileChange}
          className="file-input"
        />
        <button 
          onClick={handleUpload} 
          disabled={!selectedFile}
          className="upload-button"
        >
          Upload Video
        </button>
      </div>
      <div className="url-input-container">
        <span className="or-divider">OR</span>
        <div className="url-input-with-button">
          <input 
            type="text" 
            placeholder="Enter video URL"
            value={videoUrl}
            onChange={handleUrlChange}
            className="url-input"
          />
          <button 
            onClick={handleUpload} 
            disabled={!videoUrl}
            className="upload-button url-button"
          >
            Process URL
          </button>
        </div>
      </div>
      {selectedFile && (
        <p className="selected-file">
          Selected: {selectedFile.name}
        </p>
      )}
      {videoUrl && (
        <p className="selected-url">
          URL: {videoUrl}
        </p>
      )}
    </div>
  );
}

export default VideoUpload; 