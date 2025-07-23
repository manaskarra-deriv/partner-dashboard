import React from 'react';

const LoadingScreen = ({ message, fullscreen = false }) => {
  return (
    <div className={`loading-screen ${fullscreen ? 'fullscreen' : ''}`}>
      <div className="loading-content">
        <img 
          src="/Deriv.png" 
          alt="Deriv" 
          className="loading-logo"
        />
        <div className="loading-pulse-ring"></div>
        {message && <p className="loading-message">{message}</p>}
      </div>
    </div>
  );
};

export default LoadingScreen; 