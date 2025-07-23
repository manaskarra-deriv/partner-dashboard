import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const TierAnalytics = ({ analytics, formatCurrency, formatNumber, mainLoading = false }) => {
  const [activeChart, setActiveChart] = useState('total_earnings');

  const getTierColor = (tier) => {
    const colors = {
      'Platinum': '#E5E7EB',
      'Gold': '#FCD34D', 
      'Silver': '#9CA3AF',
      'Bronze': '#F97316'
    };
    return colors[tier] || '#6B7280';
  };

  const getChartTitle = (metric) => {
    const titles = {
      'total_earnings': 'Partner Earnings by Tier',
      'company_revenue': 'Company Revenue by Tier', 
      'active_clients': 'Active Clients by Tier'
    };
    return titles[metric] || metric;
  };

  const formatChartValue = (value, metric) => {
    if (metric === 'active_clients') {
      return formatNumber(value);
    }
    return formatCurrency(value);
  };

  const CustomTooltip = ({ active, payload, label, metric }) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip">
          <p className="tooltip-label">{`Month: ${label}`}</p>
          {payload.map((entry, index) => {
            const tierName = entry.dataKey.charAt(0).toUpperCase() + entry.dataKey.slice(1);
            let formattedValue;
            
            if (metric === 'active_clients') {
              formattedValue = formatNumber(entry.value, true); // exact formatting
            } else {
              // Format currency without decimals for cleaner display
              const roundedValue = Math.round(entry.value);
              formattedValue = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              }).format(roundedValue);
            }
            
            return (
              <p key={index} style={{ color: entry.color }}>
                {`${tierName}: ${formattedValue}`}
              </p>
            );
          })}
        </div>
      );
    }
    return null;
  };

  const RechartsBarChart = ({ data, metric }) => {
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

    return (
      <div className="simple-chart">
        <div className="chart-header">
          <h4 className="chart-title">{getChartTitle(metric)}</h4>
        </div>
        <div className="recharts-container">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={data}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
              barCategoryGap="20%"
            >
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
                  if (metric === 'active_clients') {
                    return value >= 1000 ? `${(value / 1000).toFixed(0)}K` : value;
                  }
                  return value >= 1000000 ? `$${(value / 1000000).toFixed(1)}M` : 
                         value >= 1000 ? `$${(value / 1000).toFixed(0)}K` : `$${value}`;
                }}
              />
              <Tooltip 
                content={<CustomTooltip metric={metric} />}
                cursor={{ fill: 'rgba(0, 0, 0, 0.1)' }}
              />
              <Bar dataKey="platinum" fill="#E5E7EB" name="Platinum" />
              <Bar dataKey="gold" fill="#FCD34D" name="Gold" />
              <Bar dataKey="silver" fill="#9CA3AF" name="Silver" />
              <Bar dataKey="bronze" fill="#F97316" name="Bronze" />
            </BarChart>
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
    <div className="tier-analytics">
      <div className="analytics-header">
        <h2 className="heading-lg">Tier Performance Analytics</h2>
        <p className="text-secondary">Commission breakdown and performance metrics by partner tier</p>
      </div>



      {/* Stacked Bar Charts */}
      <div className="stacked-charts-section">
        <div className="stacked-charts">
          <div className="stacked-chart">
            <div className="stacked-chart-header">
              <span className="stacked-chart-label">Commission Distribution</span>
              <span className="stacked-chart-total">{formatCurrency(analytics.totals.total_earnings)}</span>
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
              <span className="stacked-chart-total">{formatCurrency(analytics.totals.total_revenue)}</span>
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

      {/* Charts Section */}
      <div className="charts-section">
        <div className="chart-controls">
          <div className="chart-tabs">
            <button 
              className={`chart-tab ${activeChart === 'total_earnings' ? 'active' : ''}`}
              onClick={() => setActiveChart('total_earnings')}
            >
              Partner Earnings
            </button>
            <button 
              className={`chart-tab ${activeChart === 'company_revenue' ? 'active' : ''}`}
              onClick={() => setActiveChart('company_revenue')}
            >
              Company Revenue
            </button>
            <button 
              className={`chart-tab ${activeChart === 'active_clients' ? 'active' : ''}`}
              onClick={() => setActiveChart('active_clients')}
            >
              Active Clients
            </button>
          </div>
        </div>
        
        <div className="chart-container">
          <RechartsBarChart 
            data={analytics.monthly_charts[activeChart]} 
            metric={activeChart}
          />
        </div>
      </div>


    </div>
  );
};

export default TierAnalytics; 