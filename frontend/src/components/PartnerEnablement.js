import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

const PartnerEnablement = ({ 
  selectedCountry, 
  selectedRegion, 
  formatNumber, 
  navigateToPartnerDetail,
  tierProgressionData,
  setTierProgressionData,
  countryAnalysisLoading,
  setCountryAnalysisLoading
}) => {
  const loading = countryAnalysisLoading.progression;
  const [error, setError] = useState(null);
  const [showMovementModal, setShowMovementModal] = useState(false);
  const [selectedMovementData, setSelectedMovementData] = useState(null);
  const [movementModalLoading, setMovementModalLoading] = useState(false);
  const [loadingScore, setLoadingScore] = useState(null); // Track which score is loading (format: "month-type")
  const [currentDataSelection, setCurrentDataSelection] = useState(null); // Track which country/region the current data belongs to

  // Tier filter state
  const [selectedFromTier, setSelectedFromTier] = useState('All Tiers');
  const [selectedToTier, setSelectedToTier] = useState('All Tiers');
  const [appliedFromTier, setAppliedFromTier] = useState('All Tiers');
  const [appliedToTier, setAppliedToTier] = useState('All Tiers');
  const [isApplyingFilter, setIsApplyingFilter] = useState(false);

  // Available tiers for the filter
  const availableTiers = ['All Tiers', 'Bronze', 'Silver', 'Gold', 'Platinum'];

  // Fetch tier progression data
  const fetchTierProgressionData = async (country, region, fromTier = 'All Tiers', toTier = 'All Tiers') => {
    if (!country?.trim() && !region?.trim()) return;
    
    setCountryAnalysisLoading(prev => ({ ...prev, progression: true }));
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (country?.trim()) params.append('country', country.trim());
      if (region?.trim()) params.append('region', region.trim());
      if (fromTier !== 'All Tiers') params.append('from_tier', fromTier);
      if (toTier !== 'All Tiers') params.append('to_tier', toTier);
      
      const response = await axios.get(`${API_BASE_URL}/api/partner-tier-progression?${params}`);
      console.log('🔍 Tier progression API response:', response.data);
      
      if (response.data.success) {
        setTierProgressionData(response.data.data);
        setCurrentDataSelection({ country, region, fromTier, toTier }); // Track which selection this data belongs to
      } else {
        setError('Failed to fetch tier progression data');
      }
    } catch (err) {
      console.error('❌ Error fetching tier progression data:', err);
      setError('Error loading tier progression data');
      setTierProgressionData(null);
    } finally {
      setCountryAnalysisLoading(prev => ({ ...prev, progression: false }));
      setIsApplyingFilter(false);
    }
  };

  // Effect to fetch data when country/region or applied filters change
  useEffect(() => {
    if (selectedCountry?.trim() || selectedRegion?.trim()) {
      // Check if we need to fetch data for this selection
      const needsFetch = !tierProgressionData || 
                        !currentDataSelection ||
                        currentDataSelection.country !== selectedCountry ||
                        currentDataSelection.region !== selectedRegion ||
                        currentDataSelection.fromTier !== appliedFromTier ||
                        currentDataSelection.toTier !== appliedToTier;
      
      if (needsFetch) {
        fetchTierProgressionData(selectedCountry, selectedRegion, appliedFromTier, appliedToTier);
      }
    } else {
      setTierProgressionData(null);
      setCurrentDataSelection(null);
    }
  }, [selectedCountry, selectedRegion, appliedFromTier, appliedToTier]);

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

  // Apply tier filter
  const applyTierFilter = () => {
    setIsApplyingFilter(true);
    setAppliedFromTier(selectedFromTier);
    setAppliedToTier(selectedToTier);
  };

  // Fetch detailed movement data for a specific month and movement type
  const fetchMovementDetails = async (month, movementType) => {
    if (!selectedCountry && !selectedRegion) return;
    
    setMovementModalLoading(true);
    
    try {
      const params = new URLSearchParams();
      if (selectedCountry) params.append('country', selectedCountry);
      if (selectedRegion) params.append('region', selectedRegion);
      params.append('month', month);
      params.append('movement_type', movementType);
      // Add tier filters to movement details
      if (appliedFromTier !== 'All Tiers') params.append('from_tier', appliedFromTier);
      if (appliedToTier !== 'All Tiers') params.append('to_tier', appliedToTier);
      
      const response = await axios.get(`${API_BASE_URL}/api/partner-tier-movement-details?${params}`);
      console.log('🔍 Movement details API response:', response.data);
      
      if (response.data.success) {
        setSelectedMovementData({
          month,
          movementType,
          movements: response.data.data.movements || [],
          summary: response.data.data.summary || {}
        });
        setShowMovementModal(true);
      } else {
        console.error('Failed to fetch movement details');
      }
    } catch (err) {
      console.error('❌ Error fetching movement details:', err);
    } finally {
      setMovementModalLoading(false);
    }
  };

  // Handle movement score click
  const handleMovementClick = async (month, score, movementType) => {
    if (score !== 0) {
      const loadingKey = `${month}-${movementType}`;
      setLoadingScore(loadingKey);
      
      try {
        await fetchMovementDetails(month, movementType);
      } finally {
        setLoadingScore(null);
      }
    }
  };

  // Close movement modal
  const closeMovementModal = () => {
    setShowMovementModal(false);
    setSelectedMovementData(null);
  };

  // Navigate to partner detail
  const handlePartnerNavigation = (partnerId) => {
    // Close the modal first
    closeMovementModal();
    
    // Use the passed navigation function if available, otherwise fall back to event
    if (navigateToPartnerDetail) {
      navigateToPartnerDetail(partnerId);
    } else {
      // Fallback to custom event for backward compatibility
      window.dispatchEvent(new CustomEvent('switchToPartnerManagement', { 
        detail: { partnerId } 
      }));
    }
  };

  const { monthly_progression, summary } = tierProgressionData || {};

  return (
    <div className="partner-enablement-section">
      {/* Header with Filter */}
      <div className="section-header-with-controls">
        <div className="section-header-left">
          <h2 className="heading-lg">Partner Enablement - {selectedCountry || selectedRegion}</h2>
        </div>
        
        {/* Always show filter once we have country/region selected */}
        {(selectedCountry || selectedRegion) && (
          <div className="tier-filter">
            <div className="filter-controls">
              <div className="tier-transition-container">
                <div className="tier-select-group">
                  <label className="tier-sublabel">FROM</label>
                  <select 
                    className="tier-select"
                    value={selectedFromTier}
                    onChange={(e) => setSelectedFromTier(e.target.value)}
                    disabled={loading}
                  >
                    {availableTiers.map(tier => (
                      <option key={tier} value={tier}>{tier}</option>
                    ))}
                  </select>
                </div>
                
                <div className="tier-arrow">→</div>
                
                <div className="tier-select-group">
                  <label className="tier-sublabel">TO</label>
                  <select 
                    className="tier-select"
                    value={selectedToTier}
                    onChange={(e) => setSelectedToTier(e.target.value)}
                    disabled={loading}
                  >
                    {availableTiers.map(tier => (
                      <option key={tier} value={tier}>{tier}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <button 
                className="apply-filter-btn"
                onClick={applyTierFilter}
                disabled={loading || isApplyingFilter || (selectedFromTier === appliedFromTier && selectedToTier === appliedToTier)}
              >
                {isApplyingFilter ? 'Applying...' : 'Apply Filter'}
              </button>
            </div>
          </div>
        )}
        
        <div className="section-header-right">
          <p className="text-secondary">Tier progression tracking with weighted net movement for {selectedCountry || selectedRegion}</p>
        </div>
      </div>

      {/* Content Section */}
      <div className="enablement-content">
        {error ? (
          <div className="error-state">{error}</div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className={`tier-summary-cards enablement-summary-cards ${loading ? 'loading' : ''}`}>
              {loading && !tierProgressionData ? (
                // Initial loading skeleton
                Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="summary-card loading-skeleton">
                    <div className="summary-value skeleton-text"></div>
                    <div className="summary-label skeleton-text"></div>
                  </div>
                ))
              ) : tierProgressionData ? (
                <>
                  <div className="summary-card">
                    <div className={`summary-value ${getMovementClass(summary.total_positive_score)}`}>
                      {formatMovementScore(summary.total_positive_score)}
                    </div>
                    <div className="summary-label">Total Positive Tier Progression Score</div>
                  </div>
                  
                  <div className="summary-card">
                    <div className={`summary-value ${getMovementClass(summary.total_negative_score)}`}>
                      {formatMovementScore(summary.total_negative_score)}
                    </div>
                    <div className="summary-label">Total Negative Tier Progression Score</div>
                  </div>
                  
                  <div className="summary-card weighted-net-movement-card">
                    <div className={`summary-value ${getMovementClass(summary.weighted_net_movement)}`}>
                      {formatMovementScore(summary.weighted_net_movement)}
                    </div>
                    <div className="summary-label">Weighted Net Movement Across All Tiers</div>
                  </div>
                  
                  <div className="summary-card">
                    <div className="summary-value">{summary.total_months}</div>
                    <div className="summary-label">Total Months Analyzed</div>
                  </div>
                  
                  <div className="summary-card">
                    <div className={`summary-value ${getMovementClass(summary.avg_monthly_net_movement)}`}>
                      {formatMovementScore(summary.avg_monthly_net_movement.toFixed(1))}
                    </div>
                    <div className="summary-label">Average Monthly Net Movement</div>
                  </div>
                                 </>
               ) : null}
             </div>

            {/* Monthly Progression Table */}
            {tierProgressionData && monthly_progression && monthly_progression.length > 0 ? (
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
                    {monthly_progression.map((month, index) => (
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
                            onClick={() => handleMovementClick(month.month, month.positive_score, 'positive')}
                            title={month.positive_score !== 0 ? 'Click to see detailed partner movements' : ''}
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
                            onClick={() => handleMovementClick(month.month, month.negative_score, 'negative')}
                            title={month.negative_score !== 0 ? 'Click to see detailed partner movements' : ''}
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
            ) : tierProgressionData && !loading ? (
              <div className="empty-state">
                <p>No monthly tier progression data available.</p>
              </div>
            ) : null}
            

          </>
        )}
      </div>

      {/* Movement Details Modal */}
      {showMovementModal && (
        <div className="modal-overlay" onClick={closeMovementModal}>
          <div className="movement-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {selectedMovementData?.movementType === 'positive' ? 'Positive' : 'Negative'} Tier Movements - {selectedMovementData?.month}
                <div className="modal-subtitle">
                  {selectedCountry || selectedRegion} - Click on Partner ID to view details
                </div>
              </h3>
              <button className="modal-close" onClick={closeMovementModal}>×</button>
            </div>
            <div className="modal-content">
              {movementModalLoading ? (
                <div className="loading-state">
                  <div className="loading-spinner"></div>
                  Loading partner movement details...
                </div>
              ) : selectedMovementData && selectedMovementData.movements.length > 0 ? (
                <div className="movement-detail-table-container">
                  <table className="movement-detail-table">
                    <thead>
                      <tr>
                        <th>Partner ID</th>
                        <th>From Tier</th>
                        <th>To Tier</th>
                        <th>Movement Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedMovementData.movements.map((movement, index) => (
                        <tr key={index}>
                          <td>
                                                       <button 
                             className="partner-link"
                             onClick={() => handlePartnerNavigation(movement.partner_id)}
                             title="Click to view partner details"
                           >
                              {movement.partner_id}
                            </button>
                          </td>
                          <td>
                            <span className={`tier-badge ${movement.from_tier.toLowerCase()}`}>
                              {movement.from_tier}
                            </span>
                          </td>
                          <td>
                            <span className={`tier-badge ${movement.to_tier.toLowerCase()}`}>
                              {movement.to_tier}
                            </span>
                          </td>
                          <td>
                            <span className={`movement-score ${getMovementClass(movement.movement_score)}`}>
                              {formatMovementScore(movement.movement_score)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <p>No movement data available for this selection.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PartnerEnablement; 