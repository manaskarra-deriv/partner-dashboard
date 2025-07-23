import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const AIAssistant = () => {
  const [messages, setMessages] = useState([
    {
      type: 'assistant',
      content: 'Hello! I am your Partner Analytics Assistant. I can help you analyze partner data. Try asking me about "top partners", "revenue by country", or "tier distribution".',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/analytics', {
        query: userMessage.content
      });

      const assistantMessage = {
        type: 'assistant',
        content: response.data.message,
        data: response.data.data,
        dataType: response.data.type,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error getting AI response:', error);
      const errorMessage = {
        type: 'assistant',
        content: 'Sorry, I encountered an error while processing your request. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(num);
  };

  const renderDataVisualization = (data, dataType) => {
    if (!data) return null;

    switch (dataType) {
      case 'top_partners':
        return (
          <div className="data-visualization">
            <h4 className="heading-sm">Top Partners by Earnings</h4>
            <div className="partners-list">
              {data.map((partner, index) => (
                <div key={partner.partner_id} className="partner-item">
                  <div className="partner-rank">#{index + 1}</div>
                  <div className="partner-info">
                    <div className="partner-name">
                      {partner.first_name} {partner.last_name}
                    </div>
                    <div className="partner-meta">
                      <span className="partner-country">{partner.country}</span>
                      <span className={`tier-badge ${partner.partner_tier?.toLowerCase()}`}>
                        {partner.partner_tier}
                      </span>
                    </div>
                  </div>
                  <div className="partner-earnings">
                    {formatCurrency(partner.total_earnings)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'country_revenue':
        return (
          <div className="data-visualization">
            <h4 className="heading-sm">Revenue by Country</h4>
            <div className="country-revenue-list">
              {Object.entries(data)
                .sort(([,a], [,b]) => b - a)
                .map(([country, revenue]) => (
                <div key={country} className="country-revenue-item">
                  <div className="country-info">
                    <span className="country-name">{country}</span>
                  </div>
                  <div className="revenue-amount">
                    {formatCurrency(revenue)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'tier_distribution':
        return (
          <div className="data-visualization">
            <h4 className="heading-sm">Partner Tier Distribution</h4>
            <div className="tier-distribution">
              {Object.entries(data).map(([tier, count]) => (
                <div key={tier} className="tier-item">
                  <div className={`tier-badge ${tier.toLowerCase()}`}>
                    {tier}
                  </div>
                  <div className="tier-count">
                    {formatNumber(count)} partners
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const suggestedQuestions = [
    "Show me the top 10 partners",
    "What's the revenue breakdown by country?",
    "How are partners distributed across tiers?",
    "Which region has the most partners?",
    "Who are the API developer partners?"
  ];

  return (
    <div className="ai-assistant">
      <div className="chat-container">
        <div className="messages-container">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className="message-content">
                <div className="message-text">{message.content}</div>
                {message.data && renderDataVisualization(message.data, message.dataType)}
                <div className="message-timestamp">
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message assistant">
              <div className="message-content">
                <div className="thinking-indicator">
                  <div className="thinking-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span>Analyzing data...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <div className="suggested-questions">
            <div className="suggestions-label">Try asking:</div>
            <div className="suggestions-grid">
              {suggestedQuestions.map((question, index) => (
                <button
                  key={index}
                  className="suggestion-button"
                  onClick={() => setInputValue(question)}
                  disabled={isLoading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="chat-form">
            <div className="input-group">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask me about partner data..."
                className="chat-input"
                disabled={isLoading}
              />
              <button 
                type="submit" 
                className="send-button"
                disabled={isLoading || !inputValue.trim()}
              >
                {isLoading ? '⏳' : '📤'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AIAssistant; 