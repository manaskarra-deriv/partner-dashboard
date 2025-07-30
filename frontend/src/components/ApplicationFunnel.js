import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const ApplicationFunnel = ({ formatNumber, getTierColor, mainLoading = false }) => {
  const [funnelData, setFunnelData] = useState(null);
  const [tierAnalyticsData, setTierAnalyticsData] = useState(null);
  const [monthlyCountryData, setMonthlyCountryData] = useState(null);
  const [funnelLoading, setFunnelLoading] = useState(false);
  const [tierLoading, setTierLoading] = useState(false);
  const [funnelError, setFunnelError] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('');
  const [selectedTierFilter, setSelectedTierFilter] = useState('all'); // 'all', 'Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive'
  const [availableCountries, setAvailableCountries] = useState([]);
  const [availableRegions, setAvailableRegions] = useState([]);
  const [countriesLoading, setCountriesLoading] = useState(false);
  const [showTierModal, setShowTierModal] = useState(false);
  const [tierModalData, setTierModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [clickedTier, setClickedTier] = useState('');
  const [selectedTier, setSelectedTier] = useState('');
  const [selectedMonth, setSelectedMonth] = useState('');

  // Helper functions
  const formatPercentage = (value) => `${(value || 0).toFixed(1)}%`;
  const formatDays = (days) => !days ? 'N/A' : `${days} days`;

  // Helper function to get EtR ratio color class (matching PartnerTable)
  const getEtrClass = (ratio) => {
    if (ratio < 10) {
      return 'etr-critically-low'; // Purple
    } else if (ratio >= 10 && ratio < 20) {
      return 'etr-very-low'; // Blue
    } else if (ratio >= 20 && ratio < 30) {
      return 'etr-low'; // Yellow
    } else if (ratio >= 30 && ratio <= 40) {
      return 'etr-fair'; // Green
    } else if (ratio > 40) {
      return 'etr-high'; // Orange
    } else {
      return 'etr-critically-low';
    }
  };

  // Calculate summary data based on selected tier filter
  const getFilteredSummaryData = () => {
    if (!tierAnalyticsData?.monthly_tier_data) return tierAnalyticsData?.summary || {};
    
    // If 'all' is selected, return original summary
    if (selectedTierFilter === 'all') {
      return tierAnalyticsData.summary || {};
    }

    // Calculate totals for the selected tier across all months
    const months = tierAnalyticsData.available_months || [];
    let totalEarnings = 0;
    let totalRevenue = 0;
    let totalDeposits = 0;
    let totalNewClients = 0;
    let totalActiveClients = 0;
    let tierPartnerCount = 0;

    months.forEach(month => {
      const monthData = tierAnalyticsData.monthly_tier_data[month] || {};
      const tierData = monthData[selectedTierFilter] || {};
      
      totalEarnings += tierData.earnings || 0;
      totalRevenue += tierData.revenue || 0;
      totalDeposits += tierData.deposits || 0;
      totalNewClients += tierData.new_clients || 0;
      totalActiveClients += tierData.active_clients || 0;
      tierPartnerCount = Math.max(tierPartnerCount, tierData.count || 0);
    });

    // For tier-specific filtering, we'll calculate rankings at the country level
    // These will be set in the backend when we implement tier-specific country rankings
    let tierRankings = {};

    return {
      total_active_partners: tierPartnerCount,
      total_company_revenue: totalRevenue,
      total_partner_earnings: totalEarnings,
      total_deposits: totalDeposits,
      total_new_clients: totalNewClients,
      // Use country rankings for 'all', tier-specific country rankings for specific tiers
      active_partners_rank: selectedTierFilter === 'all' ? tierAnalyticsData.summary?.active_partners_rank : null, // No rank for tier count
      revenue_rank: selectedTierFilter === 'all' ? 
        tierAnalyticsData.summary?.revenue_rank : 
        tierAnalyticsData.tier_country_rankings?.[selectedTierFilter]?.revenue_rank,
      earnings_rank: selectedTierFilter === 'all' ? 
        tierAnalyticsData.summary?.earnings_rank : 
        tierAnalyticsData.tier_country_rankings?.[selectedTierFilter]?.earnings_rank,
      deposits_rank: selectedTierFilter === 'all' ? 
        tierAnalyticsData.summary?.deposits_rank : 
        tierAnalyticsData.tier_country_rankings?.[selectedTierFilter]?.deposits_rank,
      clients_rank: selectedTierFilter === 'all' ? 
        tierAnalyticsData.summary?.clients_rank : 
        tierAnalyticsData.tier_country_rankings?.[selectedTierFilter]?.new_clients_rank
    };
  };

  const getConversionClass = (rate) => {
    if (rate >= 40) return 'conversion-excellent';
    if (rate >= 25) return 'conversion-good';
    if (rate >= 15) return 'conversion-fair';
    return 'conversion-poor';
  };

  const renderMiniFunnel = (data) => {
    const total = data.applications || 0;
    const clientActivated = data.partners_activated || 0;
    const earningActivated = data.partners_earning || 0;
    
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

  // Data fetching functions
  const fetchAvailableCountries = async () => {
    try {
      setCountriesLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/partner-application-countries`);
      setAvailableCountries(response.data.countries || []);
      
      // Get unique regions from funnel data
      const funnelResponse = await axios.get(`${API_BASE_URL}/api/partner-application-funnel`);
      const regions = [...new Set(funnelResponse.data.region_distribution?.map(r => r.partner_region) || [])];
      setAvailableRegions(regions);
    } catch (err) {
      console.error('Error fetching available countries/regions:', err);
    } finally {
      setCountriesLoading(false);
    }
  };

  const fetchInitialFunnelData = async () => {
    try {
      setFunnelLoading(true);
      setFunnelError(null);
      const response = await axios.get(`${API_BASE_URL}/api/partner-application-funnel`);
      setFunnelData(response.data);
    } catch (err) {
      console.error('Error fetching initial funnel data:', err);
      setFunnelError('Failed to load application funnel data');
    } finally {
      setFunnelLoading(false);
    }
  };

  const fetchTierAnalytics = async (country, region) => {
    if (!country && !region) return;
    
    try {
      setTierLoading(true);
      const params = new URLSearchParams();
      if (country) params.append('country', country);
      if (region) params.append('region', region);
      
      const response = await axios.get(`${API_BASE_URL}/api/country-tier-analytics?${params}`);
      setTierAnalyticsData(response.data.data);
    } catch (err) {
      console.error('Error fetching tier analytics:', err);
    } finally {
      setTierLoading(false);
    }
  };

  const fetchMonthlyCountryData = async (country, region) => {
    if (!country && !region) return;
    
    try {
      const params = new URLSearchParams();
      if (country) params.append('country', country);
      if (region) params.append('region', region);
      
      const response = await axios.get(`${API_BASE_URL}/api/monthly-country-funnel?${params}`);
      setMonthlyCountryData(response.data.data);
    } catch (err) {
      console.error('Error fetching monthly country data:', err);
    }
  };

  const fetchTierDetail = async (tier, month = null) => {
    try {
      setModalLoading(true);
      const params = new URLSearchParams();
      if (selectedCountry) params.append('country', selectedCountry);
      if (selectedRegion) params.append('region', selectedRegion);
      if (tier) params.append('tier', tier);
      
      console.log('Fetching tier detail with URL:', `${API_BASE_URL}/api/tier-performance?${params}`);
      const response = await axios.get(`${API_BASE_URL}/api/tier-performance?${params}`);
      console.log('Tier performance response:', response.data);
      setTierModalData(response.data.data);
      setSelectedTier(tier);
      setSelectedMonth(month);
      setShowTierModal(true);
    } catch (err) {
      console.error('Error fetching tier performance:', err);
    } finally {
      setModalLoading(false);
      setClickedTier(''); // Clear clicked tier when done
    }
  };

  // Event handlers
  const handleCountryChange = (e) => {
    const country = e.target.value;
    setSelectedCountry(country);
    setSelectedRegion(''); // Clear region when country is selected
    if (country) {
      fetchTierAnalytics(country, null);
      fetchMonthlyCountryData(country, null);
    }
  };

  const handleRegionChange = (e) => {
    const region = e.target.value;
    setSelectedRegion(region);
    setSelectedCountry(''); // Clear country when region is selected
    if (region) {
      fetchTierAnalytics(null, region);
      fetchMonthlyCountryData(null, region);
    }
  };

  const handleTierClick = (tier, month = null) => {
    console.log('Tier clicked:', tier, 'Month:', month, 'Country:', selectedCountry, 'Region:', selectedRegion);
    setClickedTier(tier);
    fetchTierDetail(tier, month);
  };

  const closeTierModal = () => {
    setShowTierModal(false);
    setTierModalData(null);
    setSelectedTier('');
    setSelectedMonth('');
    setClickedTier('');
  };

  // Render tier tables
  const renderTierTable = (tierFilter) => {
    if (!tierAnalyticsData?.monthly_tier_data) return null;

    const months = tierAnalyticsData.available_months || [];
    const tiers = ['Platinum', 'Gold', 'Silver', 'Bronze', 'Inactive'];

    // For 'all' filter, show monthly performance across all tiers combined
    if (tierFilter === 'all') {
      return (
        <div className="tier-table-container">
          <table className="tier-table tier-detail-table">
            <thead>
              <tr>
                <th style={{textAlign: 'left'}}>Month</th>
                <th style={{textAlign: 'center'}}>Total Earnings</th>
                <th style={{textAlign: 'center'}}>Company Revenue</th>
                <th style={{textAlign: 'center'}}>EtR Ratio</th>
                <th style={{textAlign: 'center'}}>Total Deposits</th>
                <th style={{textAlign: 'center'}}>EtD Ratio</th>
                <th style={{textAlign: 'center'}}>Active Clients</th>
                <th style={{textAlign: 'center'}}>New Clients</th>
                <th style={{textAlign: 'center'}}>Volume</th>
              </tr>
            </thead>
            <tbody>
              {months.map((month, index) => {
                const monthData = tierAnalyticsData.monthly_tier_data[month] || {};
                
                // Calculate totals across all tiers for this month
                let totalEarnings = 0;
                let totalRevenue = 0;
                let totalDeposits = 0;
                let totalActiveClients = 0;
                let totalNewClients = 0;
                let totalVolume = 0;
                
                tiers.forEach(tier => {
                  const tierData = monthData[tier] || {};
                  totalEarnings += tierData.earnings || 0;
                  totalRevenue += tierData.revenue || 0;
                  totalDeposits += tierData.deposits || 0;
                  totalActiveClients += tierData.active_clients || 0;
                  totalNewClients += tierData.new_clients || 0;
                  totalVolume += tierData.volume || 0;
                });
                
                const etrRatio = totalRevenue > 0 ? ((totalEarnings / totalRevenue) * 100) : 0;
                const etdRatio = totalDeposits > 0 ? ((totalEarnings / totalDeposits) * 100) : 0;
                
                const etrClass = getEtrClass(etrRatio);
                const etdClass = 'etd-red';
                
                // Get monthly rankings for all tiers combined
                const monthlyRanks = tierAnalyticsData.monthly_rankings?.[month] || {};

                return (
                  <tr key={`totals-${month}-${index}`}>
                    <td style={{textAlign: 'left'}}><strong>{month}</strong></td>
                    <td style={{textAlign: 'center'}}>
                      <div style={{fontWeight: 'bold'}}>${formatNumber(totalEarnings)}</div>
                      {monthlyRanks.earnings_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.earnings_rank}</div>
                      )}
                    </td>
                    <td style={{textAlign: 'center'}}>
                      <div style={{fontWeight: 'bold'}}>${formatNumber(totalRevenue)}</div>
                      {monthlyRanks.revenue_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.revenue_rank}</div>
                      )}
                    </td>
                    <td style={{textAlign: 'center'}} className={etrClass}>{etrRatio.toFixed(2)}%</td>
                    <td style={{textAlign: 'center'}}>
                      <div style={{fontWeight: 'bold'}}>${formatNumber(totalDeposits)}</div>
                      {monthlyRanks.deposits_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.deposits_rank}</div>
                      )}
                    </td>
                    <td style={{textAlign: 'center'}} className={etdClass}>{etdRatio.toFixed(2)}%</td>
                    <td style={{textAlign: 'center'}}>
                      <div>{formatNumber(totalActiveClients)}</div>
                      {monthlyRanks.active_clients_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.active_clients_rank}</div>
                      )}
                    </td>
                    <td style={{textAlign: 'center'}}>
                      <div>{formatNumber(totalNewClients)}</div>
                      {monthlyRanks.new_clients_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.new_clients_rank}</div>
                      )}
                    </td>
                    <td style={{textAlign: 'center'}}>
                      <div style={{fontWeight: 'bold'}}>${formatNumber(totalVolume)}</div>
                      {monthlyRanks.volume_rank && (
                        <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.volume_rank}</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }

    // For specific tier filter, show detailed monthly performance without tier column
    return (
      <div className="tier-table-container">

        <table className="tier-table tier-detail-table">
          <thead>
            <tr>
              <th style={{textAlign: 'left'}}>Month</th>
              <th style={{textAlign: 'center'}}>Total Earnings</th>
              <th style={{textAlign: 'center'}}>Company Revenue</th>
              <th style={{textAlign: 'center'}}>EtR Ratio</th>
              <th style={{textAlign: 'center'}}>Total Deposits</th>
              <th style={{textAlign: 'center'}}>EtD Ratio</th>
              <th style={{textAlign: 'center'}}>Active Clients</th>
              <th style={{textAlign: 'center'}}>New Clients</th>
              <th style={{textAlign: 'center'}}>Volume</th>
            </tr>
          </thead>
          <tbody>
            {months.map((month, index) => {
              const monthData = tierAnalyticsData.monthly_tier_data[month] || {};
              const tierData = monthData[tierFilter] || {};
              
              // Skip if no data for this tier in this month
              if (!tierData || Object.keys(tierData).length === 0) {
                return null;
              }
              
              const earnings = tierData.earnings || 0;
              const revenue = tierData.revenue || 0;
              const deposits = tierData.deposits || 0;
              const activeClients = tierData.active_clients || 0;
              const newClients = tierData.new_clients || 0;
              const volume = tierData.volume || 0;
              
              const etrRatio = revenue > 0 ? ((earnings / revenue) * 100) : 0;
              const etdRatio = deposits > 0 ? ((earnings / deposits) * 100) : 0;

              const etrClass = getEtrClass(etrRatio);
              const etdClass = 'etd-red'; // All EtD ratios in red
              
              // Get monthly rankings
              const monthlyRanks = tierAnalyticsData.monthly_rankings?.[month] || {};

              return (
                <tr key={`detail-${month}-${index}`}>
                  <td style={{textAlign: 'left'}}><strong>{month}</strong></td>
                  <td style={{textAlign: 'center'}}>
                    <div style={{fontWeight: 'bold'}}>${formatNumber(earnings)}</div>
                    {monthlyRanks.earnings_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.earnings_rank}</div>
                    )}
                  </td>
                  <td style={{textAlign: 'center'}}>
                    <div style={{fontWeight: 'bold'}}>${formatNumber(revenue)}</div>
                    {monthlyRanks.revenue_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.revenue_rank}</div>
                    )}
                  </td>
                  <td style={{textAlign: 'center'}} className={etrClass}>{etrRatio.toFixed(2)}%</td>
                  <td style={{textAlign: 'center'}}>
                    <div style={{fontWeight: 'bold'}}>${formatNumber(deposits)}</div>
                    {monthlyRanks.deposits_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.deposits_rank}</div>
                    )}
                  </td>
                  <td style={{textAlign: 'center'}} className={etdClass}>{etdRatio.toFixed(2)}%</td>
                  <td style={{textAlign: 'center'}}>
                    <div>{formatNumber(activeClients)}</div>
                    {monthlyRanks.active_clients_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.active_clients_rank}</div>
                    )}
                  </td>
                  <td style={{textAlign: 'center'}}>
                    <div>{formatNumber(newClients)}</div>
                    {monthlyRanks.new_clients_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.new_clients_rank}</div>
                    )}
                  </td>
                  <td style={{textAlign: 'center'}}>
                    <div style={{fontWeight: 'bold'}}>${formatNumber(volume)}</div>
                    {monthlyRanks.volume_rank && (
                      <div style={{fontSize: '0.75rem', color: '#666'}}>#{monthlyRanks.volume_rank}</div>
                    )}
                  </td>
                </tr>
              );
            }).filter(Boolean)}
          </tbody>
        </table>
      </div>
    );
  };

  // Effects
  useEffect(() => {
    if (!funnelData) {
      fetchInitialFunnelData();
    }
    if (availableCountries.length === 0) {
      fetchAvailableCountries();
    }
  }, []);

  // Don't render if main app is loading
  if (mainLoading || (funnelLoading && !funnelData)) {
    return null;
  }

  return (
    <div className="application-funnel-section">
      <div className="analytics-header">
        <h2 className="heading-lg">Partner Application Funnel - Country/Region Analysis</h2>
        <p className="text-secondary">Country and GP region focused partner application analysis with tier breakdown and rankings</p>
      </div>
      
      <div className="application-funnel-content">
        {/* Country/Region Selector */}
        <div className="location-selector">
          <div className="selector-group">
            <label className="filter-label">Select Country</label>
            <select 
              value={selectedCountry} 
              onChange={handleCountryChange}
              disabled={countriesLoading || selectedRegion}
              className="location-select"
            >
              <option value="">-- Select Country --</option>
              {availableCountries.map(country => (
                <option key={country} value={country}>{country}</option>
              ))}
            </select>
          </div>
          <div className="selector-divider">OR</div>
          <div className="selector-group">
            <label className="filter-label">Select GP Region</label>
            <select 
              value={selectedRegion} 
              onChange={handleRegionChange}
              disabled={countriesLoading || selectedCountry}
              className="location-select"
            >
              <option value="">-- Select GP Region --</option>
              {availableRegions.map(region => (
                <option key={region} value={region}>{region}</option>
              ))}
            </select>
          </div>
        </div>

        {(selectedCountry || selectedRegion) && (
          <>
            {/* Tier Analytics Section */}
            {tierAnalyticsData && (
              <>
                <div className="section-divider">
                  <h3 className="section-title">Tier Analytics - {selectedCountry || selectedRegion}</h3>
                  <p className="section-subtitle">Comprehensive tier breakdown with rankings and performance metrics</p>
                </div>

                {/* Summary Cards with Rankings */}
                <div className="tier-summary-cards">
                  {(() => {
                    const summaryData = getFilteredSummaryData();
                    return (
                      <>
                        <div className="summary-card">
                          <div className="summary-value">{formatNumber(summaryData.total_active_partners || 0)}</div>
                          <div className="summary-label">
                            {selectedTierFilter === 'all' ? 'Active Partners' : `${selectedTierFilter} Partners`}
                          </div>
                          {selectedTierFilter === 'all' && summaryData.active_partners_rank && (
                            <div className="summary-rank">#{summaryData.active_partners_rank}</div>
                          )}
                        </div>
                        <div className="summary-card">
                          <div className="summary-value">${formatNumber(summaryData.total_company_revenue || 0)}</div>
                          <div className="summary-label">Deriv Revenue</div>
                          {summaryData.revenue_rank && (
                            <div className="summary-rank">#{summaryData.revenue_rank}</div>
                          )}
                        </div>
                        <div className="summary-card">
                          <div className="summary-value">${formatNumber(summaryData.total_partner_earnings || 0)}</div>
                          <div className="summary-label">Partner Earnings</div>
                          {summaryData.earnings_rank && (
                            <div className="summary-rank">#{summaryData.earnings_rank}</div>
                          )}
                        </div>
                        <div className="summary-card">
                          <div className="summary-value">${formatNumber(summaryData.total_deposits || 0)}</div>
                          <div className="summary-label">Total Deposits</div>
                          {summaryData.deposits_rank && (
                            <div className="summary-rank">#{summaryData.deposits_rank}</div>
                          )}
                        </div>
                        <div className="summary-card">
                          <div className="summary-value">{formatNumber(summaryData.total_new_clients || 0)}</div>
                          <div className="summary-label">New Clients</div>
                          {summaryData.clients_rank && (
                            <div className="summary-rank">#{summaryData.clients_rank}</div>
                          )}
                        </div>
                      </>
                    );
                  })()}
                </div>

                {/* Tier Filter Tabs */}
                <div className="tier-tabs">
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('all')}
                  >
                    Monthly Totals
                  </button>
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'Platinum' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('Platinum')}
                  >
                    <span className={`tier-badge ${getTierColor('Platinum')}`}>
                      Platinum
                    </span>
                  </button>
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'Gold' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('Gold')}
                  >
                    <span className={`tier-badge ${getTierColor('Gold')}`}>
                      Gold
                    </span>
                  </button>
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'Silver' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('Silver')}
                  >
                    <span className={`tier-badge ${getTierColor('Silver')}`}>
                      Silver
                    </span>
                  </button>
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'Bronze' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('Bronze')}
                  >
                    <span className={`tier-badge ${getTierColor('Bronze')}`}>
                      Bronze
                    </span>
                  </button>
                  <button 
                    className={`tier-tab ${selectedTierFilter === 'Inactive' ? 'active' : ''}`}
                    onClick={() => setSelectedTierFilter('Inactive')}
                  >
                    <span className={`tier-badge ${getTierColor('Inactive')}`}>
                      Inactive
                    </span>
                  </button>
                </div>

                {/* Tier Table */}
                {tierLoading ? (
                  <div className="loading-state">Loading tier analytics...</div>
                ) : (
                  renderTierTable(selectedTierFilter)
                )}
              </>
            )}

            {/* Monthly Trends Table */}
            <div className="section-divider">
              <h3 className="section-title">Monthly Trends - {selectedCountry || selectedRegion}</h3>
              <p className="section-subtitle">All months showing progression from application to client acquisition and earning generation</p>
            </div>

            {monthlyCountryData && (
              <div className="funnel-table-container">
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
                    {monthlyCountryData.monthly_data?.map((month, index) => (
                      <tr key={index}>
                        <td className="month-cell">
                          <strong>{month.month}</strong>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatNumber(month.applications)}</div>
                          <div className="funnel-rank">#{month.country_rank || 'N/A'}</div>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatNumber(month.partners_activated)}</div>
                          <div className={`funnel-percentage ${getConversionClass(month.client_activation_rate)}`}>
                            {formatPercentage(month.client_activation_rate)}
                          </div>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatNumber(month.partners_earning)}</div>
                          <div className={`funnel-percentage ${getConversionClass(month.earning_activation_rate)}`}>
                            {formatPercentage(month.earning_activation_rate)}
                          </div>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatNumber(month.sub_partners)}</div>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatDays(month.days_to_client)}</div>
                        </td>
                        <td className="funnel-cell">
                          <div className="funnel-value">{formatDays(month.days_to_earning)}</div>
                        </td>
                        <td className="funnel-viz-cell">
                          {renderMiniFunnel(month)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {!selectedCountry && !selectedRegion && (
          <div className="selection-prompt">
            <div className="prompt-content">
              <h3>Select a Country or GP Region</h3>
              <p>Choose a country or GP region above to view detailed application funnel and tier analytics data.</p>
            </div>
          </div>
        )}

        {/* Tier Detail Modal */}
        {showTierModal && (
          <div className="modal-overlay" onClick={closeTierModal}>
            <div className="tier-modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>
                  {selectedTier} Tier Performance - {selectedCountry || selectedRegion}
                  <div className="modal-subtitle">Ranked by tier by country, subscript text</div>
                </h3>
                <button className="modal-close" onClick={closeTierModal}>×</button>
              </div>
              <div className="modal-content">
                {modalLoading ? (
                  <div className="loading-state">
                    <div className="loading-spinner"></div>
                    Loading tier performance data...
                  </div>
                ) : tierModalData && tierModalData.length > 0 ? (
                  <div className="tier-detail-table-container">
                    <table className="tier-detail-table">
                      <thead>
                        <tr>
                          <th>Month</th>
                          <th>Tier</th>
                          <th>Total Earnings</th>
                          <th>Company Revenue</th>
                          <th>EtR Ratio</th>
                          <th>Total Deposits</th>
                          <th>EtD Ratio</th>
                          <th>Active Clients</th>
                          <th>New Clients</th>
                          <th>Volume</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tierModalData.map((row, index) => (
                          <tr key={index}>
                            <td>{row.month}</td>
                            <td>
                              <span className={`tier-badge ${row.tier.toLowerCase()}`}>{row.tier}</span>
                            </td>
                            <td>
                              <div className="metric-value">${formatNumber(row.total_earnings)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.earnings_rank}</div>
                              )}
                            </td>
                            <td>
                              <div className="metric-value">${formatNumber(row.company_revenue)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.revenue_rank}</div>
                              )}
                            </td>
                            <td>{row.etr_ratio}%</td>
                            <td>
                              <div className="metric-value">${formatNumber(row.total_deposits)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.deposits_rank}</div>
                              )}
                            </td>
                            <td>{row.etd_ratio}%</td>
                            <td>
                              <div className="metric-value">{formatNumber(row.active_clients)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.clients_rank}</div>
                              )}
                            </td>
                            <td>
                              <div className="metric-value">{formatNumber(row.new_clients)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.new_clients_rank}</div>
                              )}
                            </td>
                            <td>
                              <div className="metric-value">${formatNumber(row.volume)}</div>
                              {row.tier.toLowerCase() !== 'inactive' && (
                                <div className="metric-rank">#{row.volume_rank}</div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">
                    <p>No data available for the selected tier and timeframe.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {funnelError && (
          <div className="error-state">{funnelError}</div>
        )}
      </div>
    </div>
  );
};

export default ApplicationFunnel; 