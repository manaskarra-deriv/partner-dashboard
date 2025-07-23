import React from 'react';

const PartnerDetail = ({ partner, formatCurrency, formatNumber, getTierColor, onBack }) => {
  // If partner is the full API response, use it directly
  const partnerInfo = partner?.partner_info || partner;
  const monthlyPerformance = partner?.monthly_performance || [];

  // Detailed formatting functions for partner detail page (show exact decimals)
  const formatDetailCurrency = (amount) => {
    const num = Number(amount);
    if (num % 1 === 0) {
      // Whole number - no decimals
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(num);
    } else {
      // Has decimals - show exactly 2 decimal places
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(num);
    }
  };

  const formatDetailNumber = (num) => {
    const number = Number(num);
    if (number % 1 === 0) {
      // Whole number - no decimals
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(number);
    } else {
      // Has decimals - show exactly 2 decimal places
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(number);
    }
  };

  return (
    <div className="detail-container">
      {/* Header with back button */}
      <div className="detail-header-nav">
        <button 
          className="btn-secondary"
          onClick={() => onBack ? onBack() : window.history.back()}
        >
          ← Back to Dashboard
        </button>
        <h2 className="heading-lg">Partner Details</h2>
      </div>
      {/* Partner Info Header */}
      <div className="detail-header">
        <div className="partner-header-info">
          <div className="partner-avatar">
            <span className="avatar-initials">
              {partnerInfo.first_name?.[0]}{partnerInfo.last_name?.[0]}
            </span>
          </div>
          <div className="partner-basic-info">
            <h1 className="heading-xl">
              {partnerInfo.first_name} {partnerInfo.last_name}
            </h1>
            <p className="text-secondary">@{partnerInfo.username}</p>
            <div className="partner-meta">
              <span className={`tier-badge ${getTierColor(partnerInfo.partner_tier)}`}>
                {partnerInfo.partner_tier}
              </span>
              <span className="partner-id">ID: {partnerInfo.partner_id}</span>
              {partnerInfo.is_app_dev && (
                <span className="api-dev-badge">⚡ API Developer</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="detail-metrics">
        <div className="metric-card">
          <div className="metric-label">YTD Total Earnings</div>
          <div className="metric-value large">{formatDetailCurrency(partnerInfo.total_earnings || 0)}</div>
          <div className="metric-secondary">
            Monthly avg: {formatDetailCurrency(partnerInfo.avg_monthly_earnings || 0)}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Total Active Clients</div>
          <div className="metric-value large">{formatDetailNumber(partnerInfo.total_active_clients || 0)}</div>
          <div className="metric-secondary">
            Monthly avg: {formatDetailNumber(Math.round(partnerInfo.avg_monthly_active_clients || 0))}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Total New Clients</div>
          <div className="metric-value large">{formatDetailNumber(partnerInfo.total_new_clients || 0)}</div>
          <div className="metric-secondary">
            Monthly avg: {formatDetailNumber(Math.round(partnerInfo.avg_monthly_new_clients || 0))}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">YTD Company Revenue</div>
          <div className="metric-value large">{formatDetailCurrency(partnerInfo.company_revenue || 0)}</div>
          <div className="metric-secondary">
            Monthly avg: {formatDetailCurrency(partnerInfo.avg_monthly_revenue || 0)}
          </div>
        </div>
      </div>

      {/* Current Month Performance */}
      {partner.current_month && (
        <div className="current-month-section">
          <h3 className="heading-md">Current Month Performance</h3>
          <div className="current-month-metrics">
            <div className="current-month-card">
              <div className="metric-label">Month</div>
              <div className="metric-value">{new Date(partner.current_month.month).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })}</div>
            </div>
            <div className="current-month-card">
              <div className="metric-label">Earnings</div>
              <div className="metric-value">{formatDetailCurrency(partner.current_month.total_earnings || 0)}</div>
            </div>
            <div className="current-month-card">
              <div className="metric-label">Active Clients</div>
              <div className="metric-value">{formatDetailNumber(partner.current_month.active_clients || 0)}</div>
            </div>
            <div className="current-month-card">
              <div className="metric-label">New Clients</div>
              <div className="metric-value">{formatDetailNumber(partner.current_month.new_active_clients || 0)}</div>
            </div>
            <div className="current-month-card">
              <div className="metric-label">Company Revenue</div>
              <div className="metric-value">{formatDetailCurrency(partner.current_month.company_revenue || 0)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Partner Details Grid */}
      <div className="detail-grid">
        {/* Contact & Location Info */}
        <div className="detail-card">
          <h3 className="heading-md">Contact & Location</h3>
          <div className="detail-rows">
            <div className="detail-row">
              <span className="detail-label">Country</span>
              <span className="detail-value">
                {partnerInfo.country}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Region</span>
              <span className="detail-value">{partnerInfo.region}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Joined Date</span>
              <span className="detail-value">
                {partnerInfo.joined_date ? new Date(partnerInfo.joined_date).toLocaleDateString() : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Performance Info */}
        <div className="detail-card">
          <h3 className="heading-md">Performance</h3>
          <div className="detail-rows">
            <div className="detail-row">
              <span className="detail-label">Partner Tier</span>
              <span className={`tier-badge ${getTierColor(partnerInfo.partner_tier)}`}>
                {partnerInfo.partner_tier}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Tier Rewards</span>
              <span className="detail-value">{formatCurrency(partnerInfo.tier_rewards || 0)}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">API Developer</span>
              <span className={`status-badge ${partnerInfo.is_app_dev ? 'active' : 'inactive'}`}>
                {partnerInfo.is_app_dev ? '✅ Yes' : '❌ No'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Performance */}
      {monthlyPerformance.length > 0 && (
        <div className="detail-card">
          <h3 className="heading-md">Monthly Performance</h3>
          <div className="monthly-performance">
            <div className="performance-table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Tier</th>
                    <th>Total Earnings</th>
                    <th>Active Clients</th>
                    <th>New Clients</th>
                    <th>Company Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {monthlyPerformance.map((month, index) => (
                    <tr key={index}>
                      <td>
                        {month.month ? new Date(month.month).toLocaleDateString('en-US', { 
                          year: 'numeric', 
                          month: 'short' 
                        }) : 'N/A'}
                      </td>
                      <td>
                        <span className={`tier-badge ${getTierColor(month.partner_tier)}`}>
                          {month.partner_tier || 'N/A'}
                        </span>
                      </td>
                      <td className="currency-cell">
                        {formatDetailCurrency(month.total_earnings || 0)}
                      </td>
                      <td className="numeric-cell">
                        {formatDetailNumber(month.active_clients || 0)}
                      </td>
                      <td className="numeric-cell">
                        {formatDetailNumber(month.new_active_clients || 0)}
                      </td>
                      <td className="currency-cell">
                        {formatDetailCurrency(month.company_revenue || 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PartnerDetail; 