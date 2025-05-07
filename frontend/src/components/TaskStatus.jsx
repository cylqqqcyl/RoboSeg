import React from 'react';

function TaskStatus({ taskId, status, results, error, onSegmentClick }) {
  return (
    <div className="task-status">
      {taskId && (
        <div className="task-id">
          <p><strong>Task ID:</strong> {taskId}</p>
        </div>
      )}
      
      {status && (
        <div className="status">
          <h3>Status: {status}</h3>
        </div>
      )}
      
      {status === 'SUCCESS' && results && (
        <div className="results">
          <h3>Segmentation Results:</h3>
          <div className="segments-list">
            {results.map((segment, index) => (
              <div 
                key={index} 
                className="segment-item clickable"
                onClick={() => onSegmentClick(segment.start_time)}
              >
                <p>
                  <strong>Segment {index + 1}:</strong> {segment.action}
                </p>
                <p>
                  <strong>Time:</strong> {segment.start_time}s - {segment.end_time}s
                </p>
                <div className="segment-click-hint">
                  Click to jump to this segment
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {status === 'FAILURE' && error && (
        <div className="error">
          <h3>Error:</h3>
          <p>{error}</p>
        </div>
      )}
    </div>
  );
}

export default TaskStatus; 