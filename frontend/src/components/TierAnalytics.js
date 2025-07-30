import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const TierAnalytics = ({ analytics, formatCurrency, formatNumber, formatVolume, mainLoading = false }) => {
  const [activeChart, setActiveChart] = useState('company_revenue');
  const [showTrends, setShowTrends] = useState(false);
  const [funnelData, setFunnelData] = useState(null);
  const [funnelLoading, setFunnelLoading] = useState(false);
  const [funnelError, setFunnelError] = useState(null);
  const [activeFunnelTab, setActiveFunnelTab] = useState('monthly');
  const [selectedCountries, setSelectedCountries] = useState([]);
  const [selectedMonth, setSelectedMonth] = useState('all');
  const [availableCountries, setAvailableCountries] = useState([]);
  const [countriesLoading, setCountriesLoading] = useState(false);
  const [countrySearchTerm, setCountrySearchTerm] = useState('');
  const [tablesLoading, setTablesLoading] = useState(false);

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

  // Application Funnel Helper Functions
  const formatPercentage = (value) => {
    return `${(value || 0).toFixed(1)}%`;
  };

  const formatDays = (days) => {
    if (!days) return 'N/A';
    return `${days} days`;
  };

  const resetFilters = () => {
    setSelectedCountries([]);
    setSelectedMonth('all');
    setCountrySearchTerm('');
    if (funnelData) {
      fetchFunnelData(false);
    }
  };

  const filteredCountries = availableCountries.filter(country =>
    country.toLowerCase().includes(countrySearchTerm.toLowerCase())
  );

  const getConversionClass = (rate) => {
    if (rate >= 40) return 'conversion-excellent';
    if (rate >= 25) return 'conversion-good';
    if (rate >= 15) return 'conversion-fair';
    return 'conversion-poor';
  };

  const renderMiniFunnel = (data, type = 'monthly') => {
    const total = data.total_applications || 0;
    const clientActivated = data.client_activated || 0;
    const earningActivated = data.earning_activated || 0;
    
    const clientRate = total > 0 ? (clientActivated / total) * 100 : 0;
    const earningRate = total > 0 ? (earningActivated / total) * 100 : 0;
    
    const stages = [
      { value: total, percentage: 100, color: '#3B82F6', label: 'Applied' },
      { value: clientActivated, percentage: clientRate, color: '#10B981', label: 'Client Active' },
      { value: earningActivated, percentage: earningRate, color: '#F59E0B', label: 'Earning' }
    ];

    return (
      <div className="trapezoidal-funnel">
        <svg width="150" height="24" viewBox="0 0 150 24">
          {stages.map((stage, stageIdx) => {
            const maxHeight = 20;
            const minHeight = 3;
            const currentHeight = Math.max(stage.percentage / 100 * maxHeight, minHeight);
            const prevHeight = stageIdx === 0 ? maxHeight : Math.max(stages[stageIdx - 1].percentage / 100 * maxHeight, minHeight);
            
            const stageWidth = 48;
            const x = stageIdx * stageWidth + 2;
            
            const currentY = (24 - currentHeight) / 2;
            const prevY = (24 - prevHeight) / 2;
            
            let path;
            if (stageIdx === 0) {
              path = `M${x},${currentY} L${x + stageWidth - 2},${currentY} L${x + stageWidth - 2},${currentY + currentHeight} L${x},${currentY + currentHeight} Z`;
            } else {
              const prevX = (stageIdx - 1) * stageWidth + 2;
              const prevRight = prevX + stageWidth - 2;
              
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
                <title>{`${stage.label}: ${stage.value} (${stage.percentage.toFixed(1)}%)`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  // useEffects for application funnel
  useEffect(() => {
    // Load application funnel data and countries on component mount
    if (!funnelData) {
      fetchFunnelData(true);
    }
    if (availableCountries.length === 0) {
      fetchAvailableCountries();
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      const dropdown = document.getElementById('country-dropdown-content');
      const header = event.target.closest('.multi-select-header');
      if (dropdown && !header && dropdown.style.display === 'block') {
        dropdown.style.display = 'none';
        dropdown.parentElement.classList.remove('open');
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  useEffect(() => {
    if (selectedMonth && funnelData) {
      fetchFunnelData(false);
    }
  }, [selectedMonth]);

  useEffect(() => {
    if (activeFunnelTab === 'country' && funnelData) {
      fetchFunnelData(false);
    }
  }, [selectedCountries]);

  useEffect(() => {
    if (activeFunnelTab === 'monthly') {
      setSelectedMonth('all');
    }
  }, [activeFunnelTab]);

  const fetchAvailableCountries = async () => {
    try {
      setCountriesLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/partner-application-countries`);
      setAvailableCountries(response.data.countries || []);
    } catch (err) {
      console.error('Error fetching available countries:', err);
    } finally {
      setCountriesLoading(false);
    }
  };

  const fetchFunnelData = async (isInitialLoad = false) => {
    try {
      if (isInitialLoad) {
        setFunnelLoading(true);
      } else {
        setTablesLoading(true);
      }
      setFunnelError(null);
      
      let url = `${API_BASE_URL}/api/partner-application-funnel`;
      const params = new URLSearchParams();
      
      if (selectedMonth && selectedMonth !== 'all') {
        params.append('month', selectedMonth);
      }
      
      if (selectedCountries && selectedCountries.length > 0) {
        params.append('countries', selectedCountries.join(','));
      }
      
      if (params.toString()) {
        url += `?${params.toString()}`;
      }
      
      const response = await axios.get(url);
      setFunnelData(response.data);
    } catch (err) {
      console.error('Error fetching partner application funnel data:', err);
      setFunnelError('Failed to load partner application funnel data');
    } finally {
      if (isInitialLoad) {
        setFunnelLoading(false);
      } else {
        setTablesLoading(false);
      }
    }
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
  // Also wait for initial funnel data to load
  if (mainLoading || !analytics || (funnelLoading && !funnelData)) {
    return null;
  }

  return (
    <div className="tier-analytics">
      <div className="analytics-header">
        <h2 className="heading-lg">Tier Performance Analytics</h2>
        <p className="text-secondary">Commission breakdown and performance metrics by partner tier</p>
      </div>

      {/* Charts Section - Moved to top */}
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
        
        {/* Single Selected Chart */}
        <div className="chart-container">
          <RechartsChart 
            data={analytics.monthly_charts[activeChart]} 
            metric={activeChart}
          />
        </div>
      </div>

      {/* Partner Application Funnel - Separate Section */}
      <div className="application-funnel-section">
        <div className="analytics-header">
          <h2 className="heading-lg">Partner Application Funnel</h2>
          <p className="text-secondary">Partner application and activation funnel showing progression from application to client acquisition and earning generation</p>
        </div>
        
        <div className="application-funnel-content">
          {funnelLoading ? (
            <div className="loading-state">Loading application funnel data...</div>
          ) : funnelError ? (
            <div className="error-state">{funnelError}</div>
          ) : funnelData ? (
            <>
              {/* Funnel Summary Metrics */}
              <div className="funnel-summary">
                <div className="summary-card">
                  <div className="summary-value">{formatNumber(funnelData.summary?.total_applications || 0)}</div>
                  <div className="summary-label">Total Applications</div>
                  <div className="summary-sublabel">Last 12 months</div>
                </div>
                <div className="summary-card">
                  <div className="summary-value">{formatNumber(funnelData.summary?.client_activated || 0)}</div>
                  <div className="summary-label">Partners Activated</div>
                  <div className="summary-sublabel">Got first client</div>
                </div>
                <div className="summary-card">
                  <div className="summary-value">{formatPercentage(funnelData.summary?.client_activation_rate || 0)}</div>
                  <div className="summary-label">Client Activation Rate</div>
                  <div className="summary-sublabel">{formatDays(funnelData.summary?.avg_days_to_first_client || 0)} avg</div>
                </div>
                <div className="summary-card">
                  <div className="summary-value">{formatNumber(funnelData.summary?.earning_activated || 0)}</div>
                  <div className="summary-label">Partners Earning</div>
                  <div className="summary-sublabel">Generated income</div>
                </div>
                <div className="summary-card">
                  <div className="summary-value">{formatPercentage(funnelData.summary?.earning_activation_rate || 0)}</div>
                  <div className="summary-label">Earning Activation Rate</div>
                  <div className="summary-sublabel">{formatDays(funnelData.summary?.avg_days_to_first_earning || 0)} avg</div>
                </div>
                <div className="summary-card">
                  <div className="summary-value">{formatNumber(funnelData.summary?.sub_partners || 0)}</div>
                  <div className="summary-label">Sub-Partners</div>
                  <div className="summary-sublabel">vs {formatNumber(funnelData.summary?.direct_partners || 0)} direct</div>
                </div>
              </div>

              {/* Funnel Tab Navigation */}
              <div className="funnel-tabs">
                <button 
                  className={`tab-button ${activeFunnelTab === 'monthly' ? 'active' : ''}`}
                  onClick={() => setActiveFunnelTab('monthly')}
                >
                  Monthly Trends
                </button>
                <button 
                  className={`tab-button ${activeFunnelTab === 'country' ? 'active' : ''}`}
                  onClick={() => setActiveFunnelTab('country')}
                >
                  By Country
                </button>
                <button 
                  className={`tab-button ${activeFunnelTab === 'region' ? 'active' : ''}`}
                  onClick={() => setActiveFunnelTab('region')}
                >
                  By GP Region
                </button>
              </div>

              {/* Funnel Data Tables */}
              <div className="funnel-content">
                {activeFunnelTab === 'monthly' && funnelData.monthly_data && (
                  <div className="funnel-table-container" style={{position: 'relative'}}>
                    {tablesLoading && (
                      <div className="table-loading-overlay">
                        <div className="table-loading-spinner">Updating...</div>
                      </div>
                    )}
                    <table className="funnel-table">
                      <thead>
                        <tr>
                          <th>Month</th>
                          <th>Applications</th>
                          <th>Partners Activated</th>
                          <th>Partners Earning</th>
                          <th>Sub-Partners</th>
                          <th>Days to Client</th>
                          <th>Days to Earning</th>
                          <th>Funnel</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(funnelData.monthly_data || []).map((month, index) => {
                          const clientRate = month.client_activation_rate || 0;
                          const earningRate = month.earning_activation_rate || 0;

                          return (
                            <tr key={index}>
                              <td className="month-cell">
                                <strong>{month.application_month}</strong>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatNumber(month.total_applications)}
                                </div>
                                <div className="funnel-percentage">100%</div>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatNumber(month.client_activated)}
                                </div>
                                <div className={`funnel-percentage ${getConversionClass(clientRate)}`}>
                                  {formatPercentage(clientRate)}
                                </div>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatNumber(month.earning_activated)}
                                </div>
                                <div className={`funnel-percentage ${getConversionClass(earningRate)}`}>
                                  {formatPercentage(earningRate)}
                                </div>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatNumber(month.sub_partners)}
                                </div>
                                <div className="funnel-percentage">
                                  vs {formatNumber(month.direct_partners)} direct
                                </div>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatDays(month.avg_days_to_first_client)}
                                </div>
                              </td>
                              <td className="funnel-cell">
                                <div className="funnel-value">
                                  {formatDays(month.avg_days_to_first_earning)}
                                </div>
                              </td>
                              <td className="funnel-viz-cell">
                                {renderMiniFunnel(month, 'monthly')}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeFunnelTab === 'country' && funnelData.country_distribution && (
                  <>
                    {/* Country Filters */}
                    <div className="funnel-filters">
                      <button 
                        className="reset-filters-btn-small"
                        onClick={resetFilters}
                        disabled={selectedCountries.length === 0 && selectedMonth === 'all'}
                      >
                        Reset Filters
                      </button>
                      <div className="filter-group">
                        <label className="filter-label">Country</label>
                        <div className="multi-select-dropdown">
                          <div className="multi-select-header" onClick={() => {
                            const dropdown = document.getElementById('country-dropdown-content');
                            const container = dropdown.parentElement;
                            const isOpen = dropdown.style.display === 'block';
                            
                            if (isOpen) {
                              dropdown.style.display = 'none';
                              container.classList.remove('open');
                            } else {
                              dropdown.style.display = 'block';
                              container.classList.add('open');
                            }
                          }}>
                            <span className="multi-select-text">
                              {selectedCountries.length === 0 
                                ? 'All Countries' 
                                : selectedCountries.length === 1 
                                  ? selectedCountries[0]
                                  : selectedCountries.join(', ')
                              }
                            </span>
                            <span className="multi-select-arrow">▼</span>
                          </div>
                          <div id="country-dropdown-content" className="multi-select-content" style={{display: 'none'}}>
                            <div className="multi-select-search">
                              <input
                                type="text"
                                placeholder="Search countries..."
                                value={countrySearchTerm}
                                onChange={(e) => setCountrySearchTerm(e.target.value)}
                                onClick={(e) => e.stopPropagation()}
                              />
                            </div>
                            <div className="multi-select-option">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={selectedCountries.length === 0}
                                  onChange={() => {
                                    setSelectedCountries([]);
                                    setCountrySearchTerm('');
                                  }}
                                />
                                All Countries
                              </label>
                            </div>
                            {countriesLoading ? (
                              <div className="multi-select-loading">Loading countries...</div>
                            ) : (
                              filteredCountries.map(country => (
                                <div key={country} className="multi-select-option">
                                  <label>
                                    <input
                                      type="checkbox"
                                      checked={selectedCountries.includes(country)}
                                      onChange={(e) => {
                                        if (e.target.checked) {
                                          setSelectedCountries([...selectedCountries, country]);
                                        } else {
                                          setSelectedCountries(selectedCountries.filter(c => c !== country));
                                        }
                                      }}
                                    />
                                    {country}
                                  </label>
                                </div>
                              ))
                            )}
                            {!countriesLoading && filteredCountries.length === 0 && countrySearchTerm && (
                              <div className="multi-select-no-results">No countries found</div>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="filter-group">
                        <label className="filter-label">Month</label>
                        <div className="month-tabs">
                          <button 
                            className={`month-tab ${selectedMonth === 'all' ? 'active' : ''}`}
                            onClick={() => setSelectedMonth('all')}
                          >
                            All
                          </button>
                          {funnelData.monthly_data?.map(month => (
                            <button
                              key={month.application_month}
                              className={`month-tab ${selectedMonth === month.application_month ? 'active' : ''}`}
                              onClick={() => setSelectedMonth(month.application_month)}
                            >
                              {month.application_month}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    
                    <div className="funnel-table-container" style={{position: 'relative'}}>
                      {tablesLoading && (
                        <div className="table-loading-overlay">
                          <div className="table-loading-spinner">Updating...</div>
                        </div>
                      )}
                      <table className="funnel-table">
                        <thead>
                          <tr>
                            <th>Country</th>
                            <th>Applications</th>
                            <th>Partners Activated</th>
                            <th>Partners Earning</th>
                            <th>Sub-Partners</th>
                            <th>Days to Client</th>
                            <th>Days to Earning</th>
                            <th>Funnel</th>
                          </tr>
                        </thead>
                        <tbody>
                          {funnelData.country_distribution
                            ?.filter(country => 
                              selectedCountries.length === 0 || selectedCountries.includes(country.partner_country)
                            )
                            ?.slice(0, 10)
                            ?.map((country, index) => {
                              const clientRate = country.client_activation_rate || 0;
                              const earningRate = country.earning_activation_rate || 0;

                              return (
                                <tr key={index}>
                                  <td className="month-cell">
                                    <strong>{country.partner_country}</strong>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatNumber(country.total_applications)}
                                    </div>
                                    <div className="funnel-percentage">100%</div>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatNumber(country.client_activated)}
                                    </div>
                                    <div className={`funnel-percentage ${getConversionClass(clientRate)}`}>
                                      {formatPercentage(clientRate)}
                                    </div>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatNumber(country.earning_activated)}
                                    </div>
                                    <div className={`funnel-percentage ${getConversionClass(earningRate)}`}>
                                      {formatPercentage(earningRate)}
                                    </div>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatNumber(country.sub_partners)}
                                    </div>
                                    <div className="funnel-percentage">
                                      vs {formatNumber(country.total_applications - country.sub_partners)} direct
                                    </div>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatDays(country.avg_days_to_first_client)}
                                    </div>
                                  </td>
                                  <td className="funnel-cell">
                                    <div className="funnel-value">
                                      {formatDays(country.avg_days_to_first_earning)}
                                    </div>
                                  </td>
                                  <td className="funnel-viz-cell">
                                    {renderMiniFunnel(country, 'country')}
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                {activeFunnelTab === 'region' && funnelData.region_distribution && (
                  <>
                    {/* Region Filters - Only Month */}
                    <div className="funnel-filters">
                      <button 
                        className="reset-filters-btn-small"
                        onClick={resetFilters}
                        disabled={selectedMonth === 'all'}
                      >
                        Reset Filters
                      </button>
                      <div className="filter-row">
                        <div className="filter-group">
                          <label className="filter-label">Month</label>
                          <div className="month-tabs">
                            <button 
                              className={`month-tab ${selectedMonth === 'all' ? 'active' : ''}`}
                              onClick={() => setSelectedMonth('all')}
                            >
                              All
                            </button>
                            {funnelData.monthly_data?.map(month => (
                              <button
                                key={month.application_month}
                                className={`month-tab ${selectedMonth === month.application_month ? 'active' : ''}`}
                                onClick={() => setSelectedMonth(month.application_month)}
                              >
                                {month.application_month}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="funnel-table-container" style={{position: 'relative'}}>
                      {tablesLoading && (
                        <div className="table-loading-overlay">
                          <div className="table-loading-spinner">Updating...</div>
                        </div>
                      )}
                      <table className="funnel-table">
                        <thead>
                          <tr>
                            <th>GP Region</th>
                            <th>Applications</th>
                            <th>Partners Activated</th>
                            <th>Partners Earning</th>
                            <th>Sub-Partners</th>
                            <th>Days to Client</th>
                            <th>Days to Earning</th>
                            <th>Funnel</th>
                          </tr>
                        </thead>
                        <tbody>
                          {funnelData.region_distribution?.map((region, index) => {
                            const clientRate = region.client_activation_rate || 0;
                            const earningRate = region.earning_activation_rate || 0;

                            return (
                              <tr key={index}>
                                <td className="month-cell">
                                  <strong>{region.partner_region}</strong>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatNumber(region.total_applications)}
                                  </div>
                                  <div className="funnel-percentage">100%</div>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatNumber(region.client_activated)}
                                  </div>
                                  <div className={`funnel-percentage ${getConversionClass(clientRate)}`}>
                                    {formatPercentage(clientRate)}
                                  </div>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatNumber(region.earning_activated)}
                                  </div>
                                  <div className={`funnel-percentage ${getConversionClass(earningRate)}`}>
                                    {formatPercentage(earningRate)}
                                  </div>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatNumber(region.sub_partners)}
                                  </div>
                                  <div className="funnel-percentage">
                                    vs {formatNumber(region.total_applications - region.sub_partners)} direct
                                  </div>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatDays(region.avg_days_to_first_client)}
                                  </div>
                                </td>
                                <td className="funnel-cell">
                                  <div className="funnel-value">
                                    {formatDays(region.avg_days_to_first_earning)}
                                  </div>
                                </td>
                                <td className="funnel-viz-cell">
                                  {renderMiniFunnel(region, 'region')}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                {/* Fallback for empty states */}
                {!funnelData.monthly_data && activeFunnelTab === 'monthly' && (
                  <div className="empty-state">
                    <p>No monthly trend data available.</p>
                  </div>
                )}
                {!funnelData.country_distribution && activeFunnelTab === 'country' && (
                  <div className="empty-state">
                    <p>No country distribution data available.</p>
                  </div>
                )}
                {!funnelData.region_distribution && activeFunnelTab === 'region' && (
                  <div className="empty-state">
                    <p>No region distribution data available.</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="loading-state">No data available</div>
          )}
        </div>
      </div>

      {/* Stacked Bar Charts - Moved to bottom */}
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

export default TierAnalytics; 