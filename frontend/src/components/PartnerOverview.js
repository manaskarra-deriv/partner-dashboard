import React from 'react';

const PartnerOverview = ({ overview, formatCurrency, formatNumber }) => {
  if (!overview) return null;

  // Helper function to determine if a value is long and needs smaller font
  const getValueClass = (value) => {
    const length = value.replace(/[,$]/g, '').length; // Remove currency symbols and commas
    return length > 10 ? 'metric-value large-number' : 'metric-value';
  };

  const metrics = [
    {
      title: 'Active Partners',
      value: formatNumber(overview.active_partners, true),
      icon: '👥',
      color: 'metric-cyan'
    },
    {
      title: 'Total Revenue',
      value: formatCurrency(overview.total_revenue, false, true), // Use smart abbreviation
      icon: '💰',
      color: 'metric-green'
    },
    {
      title: 'Total Deposits',
      value: formatCurrency(overview.total_deposits, false, true), // Use smart abbreviation
      icon: '💳',
      color: 'metric-blue'
    },
    {
      title: 'Active Clients',
      value: formatNumber(overview.total_active_clients, true),
      icon: '👤',
      color: 'metric-purple'
    },
    {
      title: 'New Clients',
      value: formatNumber(overview.total_new_clients, true),
      icon: '✨',
      color: 'metric-orange'
    },
    {
      title: 'Avg Earnings',
      value: formatCurrency(overview.avg_earnings_per_partner, true), // Keep exact for smaller amounts
      icon: '📊',
      color: 'metric-red'
    },
    {
      title: 'API Developers',
      value: formatNumber(overview.api_developers, true),
      icon: '⚡',
      color: 'metric-yellow'
    }
  ];

  return (
    <div className="overview-grid">
      {/* Key Metrics */}
      <div className="metrics-row">
        {metrics.map((metric, index) => (
          <div key={index} className={`metric-card ${metric.color}`}>
            <div className="metric-icon">{metric.icon}</div>
            <div className="metric-content">
              <div className={getValueClass(metric.value)}>{metric.value}</div>
              <div className="metric-title">{metric.title}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Additional Insights */}
      <div className="insights-row">
        {/* Top Countries */}
        <div className="insight-card">
          <h3 className="heading-md">Top Countries</h3>
          <div className="country-list">
            {Object.entries(overview.top_countries)
              .sort(([,a], [,b]) => b - a) // Sort by count descending
              .map(([country, count]) => (
              <div key={country} className="country-item">
                <span className="country-name">{country}</span>
                <span className="country-count">{formatNumber(count, true)} partners</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tier Distribution */}
        <div className="insight-card">
          <h3 className="heading-md">Partner Tiers</h3>
          <div className="tier-list">
            {(() => {
              const tierOrder = ['Platinum', 'Gold', 'Silver', 'Bronze'];
              return tierOrder
                .filter(tier => overview.tier_distribution[tier]) // Only show tiers that exist
                .map(tier => [tier, overview.tier_distribution[tier]]);
            })().map(([tier, count]) => (
              <div key={tier} className="tier-item">
                <div className={`tier-badge ${tier.toLowerCase()}`}>
                  {tier}
                </div>
                <span className="tier-count">{formatNumber(count, true)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartnerOverview; 