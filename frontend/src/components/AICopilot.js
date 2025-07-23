import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';

const AICopilot = ({ context, data }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState(null);

  const generateInsights = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await axios.post('/api/ai-insights', {
        context: context, // 'dashboard' or 'partner_detail'
        data: data
      });
      
      setInsights(response.data);
    } catch (err) {
      console.error('Error generating insights:', err);
      setError('Failed to generate insights. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = () => {
    if (!isOpen) {
      setIsOpen(true);
      if (!insights) {
        generateInsights();
      }
    } else {
      setIsOpen(false);
    }
  };

  const handleRefresh = () => {
    setInsights(null);
    generateInsights();
  };

  return createPortal(
    <div className="ai-copilot-portal">
      {/* AI Copilot Button */}
      <button 
        className={`ai-copilot-button ${isOpen ? 'active' : ''}`}
        onClick={handleToggle}
        title="AI Insights"
      >
        <span className="ai-icon">🤖</span>
        {isLoading && <div className="loading-pulse"></div>}
      </button>

      {/* AI Copilot Popup */}
      {isOpen && (
        <div className="ai-copilot-popup">
          <div className="ai-copilot-header">
            <div className="ai-copilot-title">
              <span className="ai-icon">🤖</span>
              <h3>AI Insights</h3>
            </div>
            <div className="ai-copilot-actions">
              <button 
                className="ai-action-button" 
                onClick={handleRefresh}
                disabled={isLoading}
                title="Refresh Insights"
              >
                🔄
              </button>
              <button 
                className="ai-action-button close" 
                onClick={() => setIsOpen(false)}
                title="Close"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="ai-copilot-content">
            {isLoading ? (
              <div className="ai-loading-state">
                <div className="ai-loading-spinner"></div>
                <p>Analyzing data and generating insights...</p>
              </div>
            ) : error ? (
              <div className="ai-error-state">
                <p className="error-message">{error}</p>
                <button className="retry-button" onClick={generateInsights}>
                  Try Again
                </button>
              </div>
            ) : insights ? (
              <div className="ai-insights">
                {insights.summary && (
                  <div className="insight-section">
                    <h4>📊 Summary</h4>
                    <p>{insights.summary}</p>
                  </div>
                )}
                
                {insights.key_findings && insights.key_findings.length > 0 && (
                  <div className="insight-section">
                    <h4>🔍 Key Findings</h4>
                    <ul>
                      {insights.key_findings.map((finding, index) => (
                        <li key={index}>{finding}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {insights.recommendations && insights.recommendations.length > 0 && (
                  <div className="insight-section">
                    <h4>💡 Recommendations</h4>
                    <ul>
                      {insights.recommendations.map((rec, index) => (
                        <li key={index}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {insights.trends && insights.trends.length > 0 && (
                  <div className="insight-section">
                    <h4>📈 Trends</h4>
                    <ul>
                      {insights.trends.map((trend, index) => (
                        <li key={index}>{trend}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="ai-welcome-state">
                <p>Click to generate AI-powered insights based on the current data.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>,
    document.body
  );
};

export default AICopilot; 