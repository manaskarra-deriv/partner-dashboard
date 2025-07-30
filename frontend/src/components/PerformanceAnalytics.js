import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const PerformanceAnalytics = ({ analytics, formatCurrency, formatNumber, formatVolume, mainLoading = false }) => {
  const [activeChart, setActiveChart] = useState('company_revenue');
  const [showTrends, setShowTrends] = useState(false);

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

  const getChartTitle = (metric) => {
    const titles = {
      'total_earnings': 'Partner Earnings by Tier',
      'company_revenue': 'Company Revenue by Tier',
      'partner_id': 'Active Partners by Tier', 
      'active_clients': 'Active Clients by Tier',
      'new_active_clients': 'New Clients by Tier'
    };
    const baseTitle = titles[metric] || metric;
    return showTrends ? `${baseTitle} - Trend Analysis` : baseTitle;
  };

  const formatChartValue = (value, metric) => {
    if (metric === 'active_clients' || metric === 'new_active_clients' || metric === 'partner_id') {
      return formatNumber(value);
    }
    return formatCurrency(value);
  };

  const CustomTooltip = ({ active, payload, label, metric }) => {
    if (active && payload && payload.length) {
      // Calculate total for the month (excluding Inactive since they're always 0)
      const monthTotal = payload
        .filter(entry => entry.dataKey !== 'inactive')
        .reduce((sum, entry) => sum + entry.value, 0);

      // Format total for display
      let formattedTotal;
      if (metric === 'active_clients' || metric === 'new_active_clients' || metric === 'partner_id') {
        formattedTotal = formatNumber(monthTotal, true);
      } else {
        const roundedTotal = Math.round(monthTotal);
        formattedTotal = new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(roundedTotal);
      }

      // Define tier order from top to bottom (matching visual reading)
      const tierOrder = ['platinum', 'gold', 'silver', 'bronze'];
      
      // Sort payload according to visual stacking order
      const sortedPayload = payload
        .filter(entry => entry.dataKey !== 'inactive')
        .sort((a, b) => {
          const aIndex = tierOrder.indexOf(a.dataKey);
          const bIndex = tierOrder.indexOf(b.dataKey);
          return aIndex - bIndex;
        });

      return (
        <div className="custom-tooltip">
          <p className="tooltip-label">{`Month: ${label} | Total: ${formattedTotal}`}</p>
          {sortedPayload.map((entry, index) => {
              const tierName = entry.dataKey.charAt(0).toUpperCase() + entry.dataKey.slice(1);
              let formattedValue;
              
              if (metric === 'active_clients' || metric === 'new_active_clients' || metric === 'partner_id') {
                formattedValue = formatNumber(entry.value, true);
              } else {
                const roundedValue = Math.round(entry.value);
                formattedValue = new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                }).format(roundedValue);
              }
              
              // Calculate percentage of total for this month
              const percentage = monthTotal > 0 ? ((entry.value / monthTotal) * 100).toFixed(1) : '0.0';
              
              return (
                <p key={index} style={{ color: entry.color }}>
                  {`${tierName}: ${formattedValue} (${percentage}%)`}
                </p>
              );
            })}
        </div>
      );
    }
    return null;
  };

  const RechartsChart = ({ data, metric }) => {
    if (!data || data.length === 0) return (
      <div className="simple-chart">
        <div className="chart-header">
          <h4 className="chart-title">{getChartTitle(metric)}</h4>
        </div>
        <div className="chart-content">
          <p className="text-secondary">No data available</p>
        </div>
      </div>
    );

    const commonProps = {
      data: data,
      margin: { top: 20, right: 30, left: 20, bottom: 20 }
    };

    const commonElements = (
      <>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis 
          dataKey="month" 
          tick={{ fontSize: 12, fill: '#6b7280' }}
          tickLine={{ stroke: '#d1d5db' }}
        />
        <YAxis 
          tick={{ fontSize: 12, fill: '#6b7280' }}
          tickLine={{ stroke: '#d1d5db' }}
          tickFormatter={(value) => {
            if (metric === 'active_clients' || metric === 'new_active_clients' || metric === 'partner_id') {
              return value >= 1000 ? `${(value / 1000).toFixed(0)}K` : value;
            }
            return value >= 1000000 ? `$${(value / 1000000).toFixed(1)}M` : 
                   value >= 1000 ? `$${(value / 1000).toFixed(0)}K` : `$${value}`;
          }}
        />
        <Tooltip 
          content={<CustomTooltip metric={metric} />}
          cursor={showTrends ? { stroke: 'rgba(0, 0, 0, 0.1)' } : { fill: 'rgba(0, 0, 0, 0.1)' }}
        />
      </>
    );

    return (
      <div className="simple-chart">
        <div className="chart-header">
          <h4 className="chart-title">{getChartTitle(metric)}</h4>
        </div>
        <div className="recharts-container">
          <ResponsiveContainer width="100%" height={300}>
            {showTrends ? (
              <LineChart {...commonProps} barCategoryGap="20%">
                {commonElements}
                <Line 
                  type="monotone" 
                  dataKey="platinum" 
                  stroke="#6B7280" 
                  strokeWidth={3}
                  dot={{ fill: '#6B7280', strokeWidth: 2, r: 4 }}
                  name="Platinum" 
                />
                <Line 
                  type="monotone" 
                  dataKey="gold" 
                  stroke="#F59E0B" 
                  strokeWidth={3}
                  dot={{ fill: '#F59E0B', strokeWidth: 2, r: 4 }}
                  name="Gold" 
                />
                <Line 
                  type="monotone" 
                  dataKey="silver" 
                  stroke="#9CA3AF" 
                  strokeWidth={3}
                  dot={{ fill: '#9CA3AF', strokeWidth: 2, r: 4 }}
                  name="Silver" 
                />
                <Line 
                  type="monotone" 
                  dataKey="bronze" 
                  stroke="#EA580C" 
                  strokeWidth={3}
                  dot={{ fill: '#EA580C', strokeWidth: 2, r: 4 }}
                  name="Bronze" 
                />
                {/* Don't include Inactive in trend lines since they're all 0 */}
              </LineChart>
            ) : (
              <BarChart {...commonProps} barCategoryGap="20%">
                {commonElements}
                <Bar dataKey="bronze" stackId="a" fill="#F97316" name="Bronze" />
                <Bar dataKey="silver" stackId="a" fill="#9CA3AF" name="Silver" />
                <Bar dataKey="gold" stackId="a" fill="#FCD34D" name="Gold" />
                <Bar dataKey="platinum" stackId="a" fill="#E5E7EB" name="Platinum" />
                {/* Don't include Inactive in the chart since they're all 0 */}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  // Don't render anything if main app is loading or no data
  if (mainLoading || !analytics) {
    return null;
  }

  return (
    <div className="performance-analytics">
      <div className="analytics-header">
        <h2 className="heading-lg">Performance Analytics</h2>
        <p className="text-secondary">Monthly performance trends and tier breakdown</p>
      </div>

      {/* Charts Section */}
      <div className="charts-section">
        <div className="chart-controls">
          <div className="chart-selection">
            <h3 className="heading-md">Monthly Performance Trends</h3>
          <div className="chart-tabs">
            <button 
              className={`chart-tab ${activeChart === 'company_revenue' ? 'active' : ''}`}
              onClick={() => setActiveChart('company_revenue')}
            >
              Company Revenue
            </button>
            <button 
              className={`chart-tab ${activeChart === 'total_earnings' ? 'active' : ''}`}
              onClick={() => setActiveChart('total_earnings')}
            >
              Partner Earnings
            </button>
            <button 
              className={`chart-tab ${activeChart === 'active_clients' ? 'active' : ''}`}
              onClick={() => setActiveChart('active_clients')}
            >
              Active Clients
            </button>
            <button 
              className={`chart-tab ${activeChart === 'new_active_clients' ? 'active' : ''}`}
              onClick={() => setActiveChart('new_active_clients')}
            >
              New Clients
            </button>
            <button 
              className={`chart-tab ${activeChart === 'partner_id' ? 'active' : ''}`}
              onClick={() => setActiveChart('partner_id')}
            >
              Active Partners
            </button>
            </div>
          </div>
          
          {/* View Toggle */}
          <div className="view-toggle">
            <label className="toggle-switch">
              <span className="toggle-label">Toggle Trends</span>
              <input
                type="checkbox"
                checked={showTrends}
                onChange={(e) => setShowTrends(e.target.checked)}
              />
              <span className="toggle-slider"></span>
            </label>
          </div>
        </div>
        
        {/* Selected Chart */}
        <div className="chart-container">
          <RechartsChart 
            data={analytics.monthly_charts[activeChart]} 
            metric={activeChart}
          />
        </div>
      </div>

      {/* Stacked Bar Charts */}
      <div className="stacked-charts-section">
        <div className="stacked-charts">
          <div className="stacked-chart">
            <div className="stacked-chart-header">
              <span className="stacked-chart-label">Commission Distribution</span>
              <span className="stacked-chart-total">{formatVolume(analytics.totals.total_earnings)}</span>
            </div>
            <div className="stacked-bar">
              {analytics.tier_summary.map(tier => (
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
              <span className="stacked-chart-total">{formatVolume(analytics.totals.total_revenue)}</span>
            </div>
            <div className="stacked-bar">
              {analytics.tier_summary.map(tier => (
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
              <span className="stacked-chart-total">{formatNumber(analytics.totals.total_active_clients)}</span>
            </div>
            <div className="stacked-bar">
              {analytics.tier_summary.map(tier => (
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

export default PerformanceAnalytics; 