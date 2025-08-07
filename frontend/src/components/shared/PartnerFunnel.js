import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../../config';

const PartnerFunnel = ({ partnerId, formatNumber, formatCurrency }) => {
  const [funnelData, setFunnelData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (partnerId) {
      fetchFunnelData();
    }
  }, [partnerId]);

  const fetchFunnelData = async () => {
    try {
      setLoading(true);
      setError(null);
      
              const response = await axios.get(`${API_BASE_URL}/api/partners/${partnerId}/funnel`);
      setFunnelData(response.data);
    } catch (err) {
      console.error('Error fetching funnel data:', err);
      setError(err.response?.data?.error || 'Failed to load funnel data');
    } finally {
      setLoading(false);
    }
  };

  const formatPercentage = (value) => {
    return `${value.toFixed(1)}%`;
  };

  const getConversionClass = (rate) => {
    if (rate >= 40) return 'conversion-excellent';
    if (rate >= 25) return 'conversion-good';
    if (rate >= 15) return 'conversion-fair';
    return 'conversion-poor';
  };

  if (loading) {
    return (
      <div className="partner-funnel">
        <h3 className="heading-md">Monthly Funnel Performance</h3>
        <div className="loading-state">
          <p>Loading funnel data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="partner-funnel">
        <h3 className="heading-md">Monthly Funnel Performance</h3>
        <div className="error-state">
          <p>⚠️ {error}</p>
          <button className="btn-sm btn-primary" onClick={fetchFunnelData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!funnelData || !funnelData.funnel_data || funnelData.funnel_data.length === 0) {
    return (
      <div className="partner-funnel">
        <h3 className="heading-md">Monthly Funnel Performance</h3>
        <div className="empty-state">
          <p>No funnel data available for this partner.</p>
        </div>
      </div>
    );
  }

  const { funnel_data, summary } = funnelData;

  return (
    <div className="partner-funnel">
      <div className="funnel-header">
        <h3 className="heading-md">Monthly Funnel Performance</h3>
        <p className="funnel-description">
          Client conversion funnel segmented by joined month. Deposits/trades may occur in different months.
        </p>
      </div>

      {/* Funnel Table */}
      <div className="funnel-table-container">
        <table className="funnel-table">
          <thead>
            <tr>
              <th>Month</th>
              <th>Demo</th>
              <th>Real</th>
              <th>Deposit</th>
              <th>Traded</th>
              <th>Funnel</th>
            </tr>
          </thead>
          <tbody>
            {funnel_data.map((monthData, index) => {
              // Calculate conversion rates
              const demoToRealRate = monthData.demo_to_real_rate || 0;
              const demoToDepositRate = monthData.demo_to_deposit_rate || 0;
              const demoToTradeRate = monthData.demo_to_trade_rate || 0;

              // Funnel stages for mini visualization
              const stages = [
                { value: monthData.demo_count, percentage: 100, color: '#3B82F6' },
                { value: monthData.real_count, percentage: demoToRealRate, color: '#10B981' },
                { value: monthData.deposit_count, percentage: demoToDepositRate, color: '#F59E0B' },
                { value: monthData.traded_count, percentage: demoToTradeRate, color: '#EF4444' }
              ];

              return (
                <tr key={index}>
                  <td className="month-cell">
                    <strong>{monthData.joined_month}</strong>
                  </td>
                  <td className="funnel-cell">
                    <div className="funnel-value">
                      {formatNumber(monthData.demo_count)}
                    </div>
                    <div className="funnel-percentage">100%</div>
                  </td>
                  <td className="funnel-cell">
                    <div className="funnel-value">
                      {formatNumber(monthData.real_count)}
                    </div>
                    <div className={`funnel-percentage ${getConversionClass(demoToRealRate)}`}>
                      {formatPercentage(demoToRealRate)}
                    </div>
                  </td>
                  <td className="funnel-cell">
                    <div className="funnel-value">
                      {formatNumber(monthData.deposit_count)}
                    </div>
                    <div className={`funnel-percentage ${getConversionClass(demoToDepositRate)}`}>
                      {formatPercentage(demoToDepositRate)}
                    </div>
                  </td>
                  <td className="funnel-cell">
                    <div className="funnel-value">
                      {formatNumber(monthData.traded_count)}
                    </div>
                    <div className={`funnel-percentage ${getConversionClass(demoToTradeRate)}`}>
                      {formatPercentage(demoToTradeRate)}
                    </div>
                  </td>
                  <td className="funnel-viz-cell">
                    <div className="trapezoidal-funnel">
                      <svg width="200" height="24" viewBox="0 0 200 24">
                        {stages.map((stage, stageIdx) => {
                          // Calculate heights based on percentages for horizontal funnel
                          const maxHeight = 20;
                          const minHeight = 3;
                          const currentHeight = Math.max(stage.percentage / 100 * maxHeight, minHeight);
                          const prevHeight = stageIdx === 0 ? maxHeight : Math.max(stages[stageIdx - 1].percentage / 100 * maxHeight, minHeight);
                          
                          // Horizontal positioning - each stage takes 1/4 of the width
                          const stageWidth = 48; // 200px / 4 stages ≈ 50px per stage
                          const x = stageIdx * stageWidth + 2;
                          
                          // Center vertically
                          const currentY = (24 - currentHeight) / 2;
                          const prevY = (24 - prevHeight) / 2;
                          
                          // Create horizontal funnel trapezoid
                          let path;
                          if (stageIdx === 0) {
                            // First stage - rectangle (full height for Demo)
                            path = `M${x},${currentY} L${x + stageWidth - 2},${currentY} L${x + stageWidth - 2},${currentY + currentHeight} L${x},${currentY + currentHeight} Z`;
                          } else {
                            // Subsequent stages - trapezoid that narrows from left to right
                            const prevX = (stageIdx - 1) * stageWidth + 2;
                            const prevRight = prevX + stageWidth - 2;
                            
                            // Start from the full height of previous stage and taper to current height
                            path = `M${prevRight},${prevY} L${prevRight},${prevY + prevHeight} L${x + stageWidth - 2},${currentY + currentHeight} L${x + stageWidth - 2},${currentY} Z`;
                          }
                          
                          return (
                            <g key={stageIdx}>
                              <path
                                d={path}
                                fill={stage.color}
                                stroke="rgba(255, 255, 255, 0.8)"
                                strokeWidth="0.8"
                                opacity="0.85"
                              />
                              <title>{`${stage.value} (${stage.percentage.toFixed(1)}%)`}</title>
                            </g>
                          );
                        })}
                      </svg>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Summary Overview */}
      <div className="funnel-overview">
        <div className="overview-stats">
          <span className="overview-item">
            <strong>Total Demo Signups:</strong> {formatNumber(summary.total_demo)}
          </span>
          <span className="overview-separator">•</span>
          <span className="overview-item">
            <strong>Avg Deposit Rate:</strong> 
            <span className={`overview-rate ${getConversionClass(summary.avg_deposit_rate)}`}>
              {formatPercentage(summary.avg_deposit_rate)}
            </span>
          </span>
          <span className="overview-separator">•</span>
          <span className="overview-item">
            <strong>Avg Trade Rate:</strong>
            <span className={`overview-rate ${getConversionClass(summary.avg_trade_rate)}`}>
              {formatPercentage(summary.avg_trade_rate)}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
};

export default PartnerFunnel; 