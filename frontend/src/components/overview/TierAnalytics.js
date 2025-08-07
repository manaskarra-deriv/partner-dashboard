import React from 'react';

const TierAnalytics = ({ analytics, formatCurrency, formatNumber, formatVolume, mainLoading = false }) => {
  const getTierColor = (tier) => {
    const colors = {
      'Platinum': '#E5E7EB',
      'Gold': '#FCD34D', 
      'Silver': '#9CA3AF',
      'Bronze': '#F97316',
      'Inactive': '#9CA3AF'
    };
    return colors[tier] || '#6B7280';
  };

  // Don't render anything if main app is loading or no data
  // Also wait for initial funnel data to load
  if (mainLoading) {
    return (
      <div className="tier-analytics">
        <div className="analytics-header">
          <h2 className="heading-lg">Tier Analytics</h2>
          <p className="text-secondary">Loading tier analytics...</p>
        </div>
      </div>
    );
  }
  
  if (!analytics) {
    return null;
  }

  return (
    <div className="tier-analytics">
      <div className="analytics-header">
        <h2 className="heading-lg">Tier Analytics</h2>
        <p className="text-secondary">Comprehensive tier breakdown with rankings and performance metrics</p>
      </div>

      {/* Stacked Bar Charts */}
      <div className="stacked-charts-section">
        <div className="stacked-charts">
          <div className="stacked-chart">
            <div className="stacked-chart-header">
              <span className="stacked-chart-label">Commission Distribution</span>
              <span className="stacked-chart-total">{formatVolume(analytics?.totals?.total_earnings || 0)}</span>
            </div>
            <div className="stacked-bar">
              {(analytics?.tier_summary || []).map(tier => (
                <div 
                  key={tier.tier}
                  className={`stacked-segment tier-${tier.tier.toLowerCase()}`}
                  style={{ width: `${tier.earnings_percentage}%` }}
                  title={`${tier.tier}: ${formatCurrency(tier.total_earnings)} (${tier.earnings_percentage.toFixed(1)}%)`}
                >
                  {tier.earnings_percentage > 8 && (
                    <span className="segment-label">{tier.earnings_percentage.toFixed(1)}%</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="stacked-chart">
            <div className="stacked-chart-header">
              <span className="stacked-chart-label">Revenue Distribution</span>
              <span className="stacked-chart-total">{formatVolume(analytics?.totals?.total_revenue || 0)}</span>
            </div>
            <div className="stacked-bar">
              {(analytics?.tier_summary || []).map(tier => (
                <div 
                  key={tier.tier}
                  className={`stacked-segment tier-${tier.tier.toLowerCase()}`}
                  style={{ width: `${tier.revenue_percentage}%` }}
                  title={`${tier.tier}: ${formatCurrency(tier.total_revenue)} (${tier.revenue_percentage.toFixed(1)}%)`}
                >
                  {tier.revenue_percentage > 8 && (
                    <span className="segment-label">{tier.revenue_percentage.toFixed(1)}%</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="stacked-chart">
            <div className="stacked-chart-header">
              <span className="stacked-chart-label">Active Clients Distribution</span>
              <span className="stacked-chart-total">{formatNumber(analytics?.totals?.total_active_clients || 0)}</span>
            </div>
            <div className="stacked-bar">
              {(analytics?.tier_summary || []).map(tier => (
                <div 
                  key={tier.tier}
                  className={`stacked-segment tier-${tier.tier.toLowerCase()}`}
                  style={{ width: `${tier.clients_percentage}%` }}
                  title={`${tier.tier}: ${formatNumber(tier.active_clients)} (${tier.clients_percentage.toFixed(1)}%)`}
                >
                  {tier.clients_percentage > 8 && (
                    <span className="segment-label">{tier.clients_percentage.toFixed(1)}%</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TierAnalytics; 