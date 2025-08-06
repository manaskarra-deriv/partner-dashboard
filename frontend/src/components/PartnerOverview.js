import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const PartnerOverview = ({ 
  overview, 
  formatCurrency, 
  formatNumber,
  formatVolume,
  // Analytics props
  performanceAnalyticsData,
  tierAnalyticsData,
  performanceAnalyticsLoading,
  tierAnalyticsLoading,
  // Navigation function
  navigateToPartnerDetail,
  // Preloaded global partner enablement data
  globalTierProgressionData: preloadedGlobalTierProgressionData,
  globalProgressionLoading: preloadedGlobalProgressionLoading
}) => {
  const [activeChart, setActiveChart] = useState('company_revenue');
  const [showTrends, setShowTrends] = useState(false);
  
  // Use preloaded global partner enablement data instead of local state
  const globalTierProgressionData = preloadedGlobalTierProgressionData;
  const globalProgressionLoading = preloadedGlobalProgressionLoading;
  const [globalProgressionError, setGlobalProgressionError] = useState(null);
  
  // State for filtered global data (when tier filters are applied)
  const [filteredGlobalData, setFilteredGlobalData] = useState(null);
  const [tierFilterLoading, setTierFilterLoading] = useState(false);
  
  const [showCountryModal, setShowCountryModal] = useState(false);
  const [selectedCountryData, setSelectedCountryData] = useState(null);
  const [countryModalLoading, setCountryModalLoading] = useState(false);
  const [loadingScore, setLoadingScore] = useState(null);
  const [selectedFromTier, setSelectedFromTier] = useState('All Tiers');
  const [selectedToTier, setSelectedToTier] = useState('All Tiers');
  const [appliedFromTier, setAppliedFromTier] = useState('All Tiers');
  const [appliedToTier, setAppliedToTier] = useState('All Tiers');
  const [isApplyingFilter, setIsApplyingFilter] = useState(false);

  if (!overview) return null;

  // Helper to get current global data (preloaded or filtered)
  const getCurrentGlobalData = () => {
    return filteredGlobalData || globalTierProgressionData;
  };

  // Helper to check if global data is loading
  const isGlobalDataLoading = () => {
    return globalProgressionLoading || tierFilterLoading;
  };

  // Fetch global tier progression data (now handles filtering of preloaded data)
  const fetchGlobalTierProgressionData = async (fromTier = 'All Tiers', toTier = 'All Tiers') => {
    // If no filters applied, use the preloaded data
    if (fromTier === 'All Tiers' && toTier === 'All Tiers') {
      setFilteredGlobalData(null); // Use the main preloaded data
      setGlobalProgressionError(null);
      setIsApplyingFilter(false); // Reset applying state immediately
      return;
    }
    
    // Try client-side filtering first for better performance
    if (globalTierProgressionData && globalTierProgressionData.monthly_progression) {
      console.log('🚀 Implementing client-side filtering for tier transitions:', { fromTier, toTier });
      
      try {
        // Client-side filtering using tier transition data
        const filteredMonthlyData = globalTierProgressionData.monthly_progression.map(monthData => {
          if (!monthData.tier_transitions) {
            return monthData; // No filtering possible without transition data
          }
          
          // Filter tier transitions based on from/to tier criteria
          let filteredTransitions = Object.values(monthData.tier_transitions);
          
          if (fromTier !== 'All Tiers') {
            filteredTransitions = filteredTransitions.filter(t => t.from_tier === fromTier);
          }
          
          if (toTier !== 'All Tiers') {
            filteredTransitions = filteredTransitions.filter(t => t.to_tier === toTier);
          }
          
          // Recalculate scores and movements from filtered transitions
          let newPositiveScore = 0;
          let newNegativeScore = 0;
          let newPositiveMovements = 0;
          let newNegativeMovements = 0;
          let newTotalMovements = 0;
          
          filteredTransitions.forEach(transition => {
            if (transition.total_score > 0) {
              newPositiveScore += transition.total_score;
              newPositiveMovements += transition.count;
            } else if (transition.total_score < 0) {
              newNegativeScore += transition.total_score;
              newNegativeMovements += transition.count;
            }
            newTotalMovements += transition.count;
          });
          
          return {
            ...monthData,
            positive_score: newPositiveScore,
            negative_score: newNegativeScore,
            positive_movements: newPositiveMovements,
            negative_movements: newNegativeMovements,
            total_partners_with_movement: newTotalMovements,
            weighted_net_movement: newPositiveScore + newNegativeScore
          };
        });
        
        // Calculate new summary from filtered data
        const newSummary = {
          total_positive_score: filteredMonthlyData.reduce((sum, month) => sum + month.positive_score, 0),
          total_negative_score: filteredMonthlyData.reduce((sum, month) => sum + month.negative_score, 0),
          total_months: filteredMonthlyData.length,
          weighted_net_movement: 0
        };
        newSummary.weighted_net_movement = newSummary.total_positive_score + newSummary.total_negative_score;
        newSummary.avg_monthly_net_movement = newSummary.weighted_net_movement / newSummary.total_months;
        
        // Create filtered data object
        const clientFilteredData = {
          monthly_progression: filteredMonthlyData,
          summary: newSummary
        };
        
        console.log('✅ Client-side filtering complete:', { 
          originalTotal: globalTierProgressionData.summary.weighted_net_movement,
          filteredTotal: newSummary.weighted_net_movement 
        });
        
        setFilteredGlobalData(clientFilteredData);
        setIsApplyingFilter(false);
        setGlobalProgressionError(null);
        return; // Success! No need for API call
        
      } catch (err) {
        console.error('❌ Client-side filtering failed:', err);
        setIsApplyingFilter(false);
        // Fall through to API call
      }
    }
    
    // Apply tier filters by fetching filtered data from API
    setTierFilterLoading(true);
    setGlobalProgressionError(null);
    
    try {
      const params = new URLSearchParams();
      params.append('is_global', 'true');
      if (fromTier !== 'All Tiers') {
        params.append('from_tier', fromTier);
      }
      if (toTier !== 'All Tiers') {
        params.append('to_tier', toTier);
      }
      
      const url = `${API_BASE_URL}/api/partner-tier-progression?${params.toString()}`;
      const response = await axios.get(url);
      console.log('🔍 Filtered global tier progression API response:', response.data);
      
      if (response.data.success) {
        setFilteredGlobalData(response.data.data);
      } else {
        setGlobalProgressionError('Failed to fetch filtered global tier progression data');
      }
    } catch (err) {
      console.error('❌ Error fetching filtered global tier progression data:', err);
      setGlobalProgressionError('Error loading filtered global tier progression data');
      setFilteredGlobalData(null);
    } finally {
      setTierFilterLoading(false);
      setIsApplyingFilter(false); // Reset applying state when filtering completes
    }
  };

  // Fetch country breakdown for a specific month and movement type
  const fetchCountryBreakdown = async (month, movementType) => {
    setCountryModalLoading(true);
    
    try {
      const params = new URLSearchParams();
      params.append('month', month);
      params.append('movement_type', movementType);
      if (appliedFromTier !== 'All Tiers') {
        params.append('from_tier', appliedFromTier);
      }
      if (appliedToTier !== 'All Tiers') {
        params.append('to_tier', appliedToTier);
      }
      
      console.log('🔍 Fetching country breakdown for:', { month, movementType, fromTier: appliedFromTier, toTier: appliedToTier });
      const response = await axios.get(`${API_BASE_URL}/api/global-tier-progression-countries?${params}`);
      console.log('🔍 Country breakdown API response:', response.data);
      
      if (response.data.success) {
        console.log('✅ Countries data received:', response.data.data.countries);
        console.log('📊 Total countries:', response.data.data.total_countries);
        
        setSelectedCountryData({
          month,
          movementType,
          countries: response.data.data.countries || [],
          totalCountries: response.data.data.total_countries || 0
        });
        setShowCountryModal(true);
      } else {
        console.error('❌ API returned error:', response.data);
      }
    } catch (err) {
      console.error('❌ Error fetching country breakdown:', err);
    } finally {
      setCountryModalLoading(false);
    }
  };

  // Handle movement score click for global data
  const handleGlobalMovementClick = async (month, score, movementType) => {
    if (score !== 0) {
      const currentData = getCurrentGlobalData();
      
      // Check if we have pre-calculated country breakdowns
      const monthData = currentData?.monthly_progression?.find(m => m.month === month);
      
      if (monthData?.country_breakdowns) {
        // Use pre-calculated data - instant display! (includes filtered data)
        const countries = monthData.country_breakdowns[movementType] || [];
        
        console.log('✅ Using pre-calculated country data for:', { month, movementType, countries: countries.length });
        
        setSelectedCountryData({
          month,
          movementType,
          countries,
          total_countries: countries.length
        });
        setShowCountryModal(true);
      } else {
        // API call required (if pre-calculation failed)
        console.log('🔄 Making API call for country breakdown (pre-calculation failed)');
        const loadingKey = `${month}-${movementType}`;
        setLoadingScore(loadingKey);
        
        try {
          await fetchCountryBreakdown(month, movementType);
        } finally {
          setLoadingScore(null);
        }
      }
    }
  };

  // Close country modal
  const closeCountryModal = () => {
    setShowCountryModal(false);
    setSelectedCountryData(null);
  };

  // Apply tier filter
  const applyTierFilter = () => {
    setIsApplyingFilter(true);
    setAppliedFromTier(selectedFromTier);
    setAppliedToTier(selectedToTier);
  };

  // Effect to fetch global data on component mount and when applied filters change
  useEffect(() => {
    fetchGlobalTierProgressionData(appliedFromTier, appliedToTier);
  }, [appliedFromTier, appliedToTier]);

  // Helper function to determine if a value is long and needs smaller font
  const getValueClass = (value) => {
    const length = value.replace(/[,$]/g, '').length; // Remove currency symbols and commas
    return length > 10 ? 'metric-value large-number' : 'metric-value';
  };

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

  // Helper function to get movement badge class
  const getMovementClass = (score) => {
    if (score > 0) return 'movement-positive';
    if (score < 0) return 'movement-negative';
    return 'movement-neutral';
  };

  // Helper function to format movement score with + for positive
  const formatMovementScore = (score) => {
    if (score === null || score === undefined || isNaN(score)) return '0';
    if (score > 0) return `+${score}`;
    return score.toString();
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

      {/* Analytics Row - Performance Analytics and Tier Analytics in one row */}
      <div className="analytics-row">
        {/* Performance Analytics */}
        <div className="analytics-card performance-analytics-card">
          {performanceAnalyticsLoading ? (
            <div className="analytics-loading">
              <h3 className="heading-md">Performance Analytics</h3>
              <p className="text-secondary">Loading monthly performance trends...</p>
            </div>
          ) : performanceAnalyticsData ? (
            <>
              <div className="analytics-header">
                <h3 className="heading-md">Monthly Performance Trends</h3>
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
              
              <div className="chart-controls">
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
              
              <div className="chart-container">
                <RechartsChart 
                  data={performanceAnalyticsData?.monthly_charts?.[activeChart]} 
                  metric={activeChart}
                />
              </div>
            </>
          ) : null}
        </div>

        {/* Tier Analytics */}
        <div className="analytics-card tier-analytics-card">
          {tierAnalyticsLoading ? (
            <div className="analytics-loading">
              <h3 className="heading-md">Tier Analytics</h3>
              <p className="text-secondary">Loading tier analytics...</p>
            </div>
          ) : tierAnalyticsData ? (
            <>
              <div className="analytics-header">
                <h3 className="heading-md">Tier Analytics</h3>
                <p className="text-secondary">Comprehensive tier breakdown with rankings and performance metrics</p>
              </div>

              <div className="stacked-charts">
                <div className="stacked-chart">
                  <div className="stacked-chart-header">
                    <span className="stacked-chart-label">Commission Distribution</span>
                    <span className="stacked-chart-total">{formatVolume(tierAnalyticsData?.totals?.total_earnings || 0)}</span>
                  </div>
                  <div className="stacked-bar">
                    {(tierAnalyticsData?.tier_summary || []).map(tier => (
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
                    <span className="stacked-chart-total">{formatVolume(tierAnalyticsData?.totals?.total_revenue || 0)}</span>
                  </div>
                  <div className="stacked-bar">
                    {(tierAnalyticsData?.tier_summary || []).map(tier => (
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
                    <span className="stacked-chart-total">{formatNumber(tierAnalyticsData?.totals?.total_active_clients || 0)}</span>
                  </div>
                  <div className="stacked-bar">
                    {(tierAnalyticsData?.tier_summary || []).map(tier => (
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
            </>
          ) : null}
        </div>
      </div>

      {/* Global Partner Enablement Section */}
      <div className="global-enablement-section">
        <div className="section-header-with-controls">
          <div className="section-header-left">
            <h2 className="heading-lg">Global Partner Enablement</h2>
          </div>
          {/* Always show filter once initial data is loaded, even during subsequent loading */}
          {(globalTierProgressionData || (!globalProgressionLoading && !globalProgressionError)) && (
            <div className="tier-filter">
              <div className="filter-header">
                <span className="filter-label">Filter by Tier Transition</span>
              </div>
              <div className="filter-controls">
                <div className="tier-transition-container">
                  <div className="tier-select-group">
                    <label className="tier-sublabel">From</label>
                    <select 
                      className="tier-select"
                      value={selectedFromTier}
                      onChange={(e) => setSelectedFromTier(e.target.value)}
                      disabled={globalProgressionLoading}
                    >
                      <option value="All Tiers">All Tiers</option>
                      <option value="Platinum">Platinum</option>
                      <option value="Gold">Gold</option>
                      <option value="Silver">Silver</option>
                      <option value="Bronze">Bronze</option>
                      <option value="Inactive">Inactive</option>
                    </select>
                  </div>
                  <div className="tier-arrow">→</div>
                  <div className="tier-select-group">
                    <label className="tier-sublabel">To</label>
                    <select 
                      className="tier-select"
                      value={selectedToTier}
                      onChange={(e) => setSelectedToTier(e.target.value)}
                      disabled={globalProgressionLoading}
                    >
                      <option value="All Tiers">All Tiers</option>
                      <option value="Platinum">Platinum</option>
                      <option value="Gold">Gold</option>
                      <option value="Silver">Silver</option>
                      <option value="Bronze">Bronze</option>
                      <option value="Inactive">Inactive</option>
                    </select>
                  </div>
                </div>
                <button 
                  className="apply-filter-btn"
                  onClick={applyTierFilter}
                  disabled={isGlobalDataLoading() || isApplyingFilter}
                >
                  {isApplyingFilter || tierFilterLoading ? (
                    <>
                      <div className="loading-spinner"></div>
                      <span>Applying...</span>
                    </>
                  ) : (
                    <span>Apply Filter</span>
                  )}
                </button>
              </div>
            </div>
          )}
          <div className="section-header-right">
            <p className="text-secondary">Tier progression tracking with weighted net movement across all countries on a monthly basis</p>
          </div>
        </div>

        {/* Content Section */}
        <div className="enablement-content">
          {globalProgressionError ? (
            <div className="error-state">{globalProgressionError}</div>
          ) : (
            <>
              {/* Summary Cards */}
              <div className={`tier-summary-cards enablement-summary-cards ${isGlobalDataLoading() ? 'loading' : ''}`}>
                {isGlobalDataLoading() && !getCurrentGlobalData() ? (
                  // Initial loading skeleton
                  Array.from({ length: 5 }).map((_, index) => (
                    <div key={index} className="summary-card loading-skeleton">
                      <div className="summary-value skeleton-text"></div>
                      <div className="summary-label skeleton-text"></div>
                    </div>
                  ))
                ) : getCurrentGlobalData() && getCurrentGlobalData().summary ? (
                  <>
                    <div className="summary-card">
                      <div className={`summary-value ${getMovementClass(getCurrentGlobalData().summary.total_positive_score)}`}>
                        {formatMovementScore(getCurrentGlobalData().summary.total_positive_score)}
                      </div>
                      <div className="summary-label">Total Positive Tier Progression Score</div>
                    </div>
                    
                    <div className="summary-card">
                      <div className={`summary-value ${getMovementClass(getCurrentGlobalData().summary.total_negative_score)}`}>
                        {formatMovementScore(getCurrentGlobalData().summary.total_negative_score)}
                      </div>
                      <div className="summary-label">Total Negative Tier Progression Score</div>
                    </div>
                    
                    <div className="summary-card weighted-net-movement-card">
                      <div className={`summary-value ${getMovementClass(getCurrentGlobalData().summary.weighted_net_movement)}`}>
                        {formatMovementScore(getCurrentGlobalData().summary.weighted_net_movement)}
                      </div>
                      <div className="summary-label">Weighted Net Movement Across All Tiers</div>
                    </div>
                    
                    <div className="summary-card">
                      <div className="summary-value">{getCurrentGlobalData().summary.total_months}</div>
                      <div className="summary-label">Total Months Analyzed</div>
                    </div>
                    
                    <div className="summary-card">
                      <div className={`summary-value ${getMovementClass(getCurrentGlobalData().summary.avg_monthly_net_movement)}`}>
                        {formatMovementScore(getCurrentGlobalData().summary.avg_monthly_net_movement.toFixed(1))}
                      </div>
                      <div className="summary-label">Average Monthly Net Movement</div>
                    </div>
                  </>
                ) : null}
              </div>

              {/* Monthly Progression Table */}
              {getCurrentGlobalData() && getCurrentGlobalData().monthly_progression && getCurrentGlobalData().monthly_progression.length > 0 ? (
                <div className="tier-progression-table-container">
                  <table className="tier-progression-table">
                    <thead>
                      <tr>
                        <th style={{textAlign: 'left'}}>Month</th>
                        <th style={{textAlign: 'center'}}>Partners with Movement</th>
                        <th style={{textAlign: 'center'}}>Positive Tier Progression Score</th>
                        <th style={{textAlign: 'center'}}>Negative Tier Progression Score</th>
                        <th style={{textAlign: 'center'}}>Weighted Net Movement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getCurrentGlobalData().monthly_progression.map((month, index) => (
                        <tr key={`${month.month}-${index}`}>
                          <td style={{textAlign: 'left'}}>
                            <strong>{month.month}</strong>
                          </td>
                          <td style={{textAlign: 'center'}}>
                            <div className="progression-value">{month.total_partners_with_movement}</div>
                          </td>
                          <td style={{textAlign: 'center'}}>
                            <div 
                              className={`progression-value ${getMovementClass(month.positive_score)} ${month.positive_score !== 0 ? 'clickable' : ''} ${loadingScore === `${month.month}-positive` ? 'loading' : ''}`}
                              onClick={() => handleGlobalMovementClick(month.month, month.positive_score, 'positive')}
                              title={month.positive_score !== 0 ? 'Click to see country breakdown' : ''}
                            >
                              {formatMovementScore(month.positive_score)}
                              {loadingScore === `${month.month}-positive` && (
                                <span style={{marginLeft: '8px', display: 'inline-block'}}>
                                  <div style={{
                                    width: '12px',
                                    height: '12px',
                                    border: '2px solid rgba(255, 255, 255, 0.3)',
                                    borderTop: '2px solid #ffffff',
                                    borderRadius: '50%',
                                    animation: 'spin 0.6s linear infinite',
                                    display: 'inline-block'
                                  }}></div>
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{textAlign: 'center'}}>
                            <div 
                              className={`progression-value ${getMovementClass(month.negative_score)} ${month.negative_score !== 0 ? 'clickable' : ''} ${loadingScore === `${month.month}-negative` ? 'loading' : ''}`}
                              onClick={() => handleGlobalMovementClick(month.month, month.negative_score, 'negative')}
                              title={month.negative_score !== 0 ? 'Click to see country breakdown' : ''}
                            >
                              {formatMovementScore(month.negative_score)}
                              {loadingScore === `${month.month}-negative` && (
                                <span style={{marginLeft: '8px', display: 'inline-block'}}>
                                  <div style={{
                                    width: '12px',
                                    height: '12px',
                                    border: '2px solid rgba(255, 255, 255, 0.3)',
                                    borderTop: '2px solid #ffffff',
                                    borderRadius: '50%',
                                    animation: 'spin 0.6s linear infinite',
                                    display: 'inline-block'
                                  }}></div>
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{textAlign: 'center'}}>
                            <div className={`progression-value weighted-movement ${getMovementClass(month.weighted_net_movement)}`}>
                              <strong>{formatMovementScore(month.weighted_net_movement)}</strong>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : getCurrentGlobalData() && !globalProgressionLoading ? (
                <div className="empty-state">
                  <p>No monthly tier progression data available.</p>
                </div>
              ) : null}
              

            </>
          )}
        </div>
      </div>

      {/* Country Breakdown Modal */}
      {showCountryModal && (
        <div className="modal-overlay" onClick={closeCountryModal}>
          <div className="movement-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {selectedCountryData?.movementType === 'positive' ? 'Most Positive' : 'Most Negative'} Countries - {selectedCountryData?.month}
                <div className="modal-subtitle">
                  Global tier progression breakdown by country - Click on country name to analyze
                </div>
              </h3>
              <button className="modal-close" onClick={closeCountryModal}>×</button>
            </div>
            <div className="modal-content">
              {countryModalLoading ? (
                <div className="loading-state">
                  <div className="loading-spinner"></div>
                  Loading country breakdown...
                </div>
              ) : selectedCountryData && selectedCountryData.countries.length > 0 ? (
                <div className="movement-detail-table-container">
                  <table className="movement-detail-table">
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Country</th>
                        <th>Partners with Movement</th>
                        <th>Net Movement</th>
                        <th>Progression Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedCountryData.countries.map((country, index) => (
                        <tr key={index}>
                          <td>
                            <span className="rank-badge">#{index + 1}</span>
                          </td>
                          <td>
                            <span className="country-name">{country.country}</span>
                          </td>
                          <td>
                            <span className="partner-count">{country.partners_with_movement}</span>
                          </td>
                          <td>
                            <span className={`movement-score ${getMovementClass(country.net_movement)}`}>
                              {formatMovementScore(country.net_movement)}
                            </span>
                          </td>
                          <td>
                            <span className={`movement-score ${getMovementClass(country.score)}`}>
                              {formatMovementScore(country.score)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <p>No country data available for this selection.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PartnerOverview; 