import React from 'react';
import Pagination from './Pagination';

const PartnerTable = ({ 
  partners, 
  loading, 
  onPartnerSelect,
  formatCurrency,
  formatNumber,
  formatVolume,
  getTierColor,
  sortField,
  sortDirection,
  onSortChange,
  activeFilters,
  showPII = true,
  onRequestPIIAccess, // New prop for requesting PII access
  // Pagination props
  currentPage,
  totalPages,
  totalCount,
  partnersPerPage,
  onPageChange,
  mainLoading = false,
  // New props for CSV export
  allFilteredPartners = [], // All partners matching current filters (not just current page)
  onExportCSV // Function to get all filtered data for export
}) => {
  const getSortIcon = (field) => {
    if (sortField !== field) {
      return <span className="sort-icon sort-both">▲▼</span>;
    }
    return sortDirection === 'asc' ? 
      <span className="sort-icon sort-asc">▲</span> : 
      <span className="sort-icon sort-desc">▼</span>;
  };

  // CSV Export functionality
  const exportToCSV = async () => {
    try {
      let dataToExport = allFilteredPartners;
      
      // If no export function provided, use current page data as fallback
      if (onExportCSV && typeof onExportCSV === 'function') {
        console.log('🔄 Fetching all filtered data for CSV export...');
        dataToExport = await onExportCSV();
      } else if (allFilteredPartners.length === 0) {
        dataToExport = partners; // Use current page as fallback
      }

      if (!dataToExport || dataToExport.length === 0) {
        alert('No data available to export');
        return;
      }

      // Prepare CSV headers
      const headers = [
        'Partner ID',
        'First Name', 
        'Last Name',
        'Username',
        'Country',
        'GP Region',
        'Tier',
        'Total Earnings',
        'Company Revenue',
        'Avg Past 3 Months Earnings',
        'EtR Ratio (%)',
        'Active Clients',
        'New Clients',
        'Volume (USD)',
        'API Developer'
      ];

      // Prepare CSV rows
      const csvRows = dataToExport.map(partner => [
        partner.partner_id || '',
        partner.first_name || '',
        partner.last_name || '',
        partner.username || '',
        partner.country || '',
        partner.region || '',
        partner.partner_tier || '',
        partner.total_earnings || 0,
        partner.company_revenue || 0,
        partner.avg_past_3_months_earnings || 0,
        calculateRatioPercentage(partner.total_earnings || 0, partner.company_revenue || 0),
        partner.active_clients || 0,
        partner.new_active_clients || 0,
        partner.volume_usd || 0,
        partner.is_app_dev ? 'Yes' : 'No'
      ]);

      // Create CSV content
      const csvContent = [
        headers.join(','),
        ...csvRows.map(row => 
          row.map(field => {
            // Handle fields that might contain commas or quotes
            const stringField = String(field);
            if (stringField.includes(',') || stringField.includes('"') || stringField.includes('\n')) {
              return `"${stringField.replace(/"/g, '""')}"`;
            }
            return stringField;
          }).join(',')
        )
      ].join('\n');

      // Create and download file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      
      if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        
        // Generate filename with current timestamp and filter info
        const timestamp = new Date().toISOString().split('T')[0];
        const activeFilterCount = Object.values(activeFilters || {}).filter(f => 
          f && f !== 'All Countries' && f !== 'All GP Regions' && f !== 'All Tiers'
        ).length;
        const filterSuffix = activeFilterCount > 0 ? `_filtered_${activeFilterCount}` : '';
        
        link.setAttribute('download', `partners_export_${timestamp}${filterSuffix}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log(`✅ CSV exported: ${dataToExport.length} partners`);
      }
    } catch (error) {
      console.error('❌ Error exporting CSV:', error);
      alert('Error exporting CSV. Please try again.');
    }
  };

  const maskPII = (text, type = 'default') => {
    if (showPII) return text;
    
    if (!text) return text;
    
    switch (type) {
      case 'name':
        return '••••••';
      case 'username':
        return '@••••••';
      case 'id':
        return '••••••••';
      case 'email':
        return '••••••@••••••';
      default:
        return text.toString().replace(/./g, '•');
    }
  };

  // Calculate EtR ratio percentage with proper negative logic
  const calculateRatioPercentage = (earnings, revenue) => {
    if (!revenue || revenue === 0) return '0.0%';
    const ratio = (earnings / revenue) * 100;
    const absRatio = Math.abs(ratio);
    
    let formattedRatio;
    if (absRatio >= 1000000000) {
      formattedRatio = `${(absRatio / 1000000000).toFixed(1)}B`;
    } else if (absRatio >= 1000000) {
      formattedRatio = `${(absRatio / 1000000).toFixed(1)}M`;
    } else if (absRatio >= 1000) {
      formattedRatio = `${(absRatio / 1000).toFixed(1)}K`;
    } else {
      formattedRatio = absRatio.toFixed(1);
    }
    
    // Double negative: When revenue is negative (company lost money)
    if (revenue < 0) {
      return `--${formattedRatio}%`;
    }
    // Single negative: When earnings > positive revenue (unprofitable partner)
    else if (earnings > revenue) {
      return `-${formattedRatio}%`;
    }
    // Positive: When earnings <= revenue (profitable partner)
    else {
      return `${formattedRatio}%`;
    }
  };

  // Get EtR ratio color class based on percentage value
  const getEtrColorClass = (earnings, revenue) => {
    if (!revenue || revenue === 0) return 'etr-critically-low';
    const ratio = (earnings / revenue) * 100;
    
    // Red for any loss scenario (revenue negative OR earnings > positive revenue)
    if (revenue < 0) {
      return 'etr-double-loss';
    } else if (earnings > revenue) {
      return 'etr-unprofitable';
    } else if (ratio >= 0.1 && ratio < 10) {
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

  if (loading && !mainLoading) {
    return (
      <div className="table-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading partners...</p>
        </div>
      </div>
    );
  }

  // Don't render anything if main app is loading
  if (mainLoading) {
    return null;
  }

  if (partners.length === 0) {
    return (
      <div className="table-container">
        <div className="empty-state">
          <p>No partners found matching the current filters.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`table-wrapper ${!showPII ? 'pii-hidden' : ''}`}>
      <div className="table-header">
        <h3 className="heading-md">Partners ({formatNumber(totalCount || partners.length)})</h3>
        
        <div className="table-header-actions">
        {/* Export CSV Button - Only visible when PII is enabled */}
        {showPII && (
          <button 
            className="btn-sm btn-primary export-csv-btn"
            onClick={exportToCSV}
            title="Export all filtered partners to CSV"
            disabled={loading}
          >
            📊 Export CSV
          </button>
        )}
        
        {/* Pagination Controls in Header */}
        {totalCount > 0 && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalCount={totalCount}
            partnersPerPage={partnersPerPage}
            onPageChange={onPageChange}
            showingCount={partners.length}
          />
        )}
        </div>
      </div>
      
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>
                Partner ID
              </th>
              <th>
                Name
              </th>
              <th>
                Country
              </th>
              <th>
                GP Region
              </th>
              <th>
                Tier
              </th>
              <th onClick={() => onSortChange('total_earnings')} className="sortable">
                Total Earnings {getSortIcon('total_earnings')}
              </th>
              <th onClick={() => onSortChange('etr_ratio')} className="sortable">
                EtR {getSortIcon('etr_ratio')}
              </th>
              <th onClick={() => onSortChange('active_clients')} className="sortable">
                Active Clients {getSortIcon('active_clients')}
              </th>
              <th onClick={() => onSortChange('new_active_clients')} className="sortable">
                New Clients {getSortIcon('new_active_clients')}
              </th>
              <th onClick={() => onSortChange('volume_usd')} className="sortable">
                Volume {getSortIcon('volume_usd')}
              </th>
              <th>API Dev</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {partners.map((partner, index) => (
              <tr key={partner.partner_id || index} className="table-row">
                <td className="partner-id">
                  <span className={`mono-text ${!showPII ? 'pii-sensitive' : ''}`}>
                    {maskPII(partner.partner_id, 'id')}
                  </span>
                </td>
                <td className="partner-name">
                  <div className="name-cell">
                    <strong className={!showPII ? 'pii-sensitive' : ''}>
                      {maskPII(`${partner.first_name} ${partner.last_name}`, 'name')}
                    </strong>
                    <small className={`text-secondary ${!showPII ? 'pii-sensitive' : ''}`}>
                      {maskPII(`@${partner.username}`, 'username')}
                    </small>
                  </div>
                </td>
                <td>
                  {partner.country}
                </td>
                <td>
                  <span className="region-badge">{partner.region}</span>
                </td>
                <td>
                  <span className={`tier-badge ${getTierColor(partner.partner_tier)}`}>
                    {partner.partner_tier}
                  </span>
                </td>
                <td className="currency-cell">
                  <strong>{formatVolume(partner.total_earnings || 0)}</strong>
                  {partner.avg_past_3_months_earnings && (
                    <small className="text-secondary">
                      Avg: {formatVolume(partner.avg_past_3_months_earnings)}
                    </small>
                  )}
                </td>
                <td className="ratio-cell">
                  <span className={`etr-ratio ${getEtrColorClass(
                    partner.total_earnings || 0, 
                    partner.company_revenue || 0
                  )}`}>
                    {calculateRatioPercentage(
                      partner.total_earnings || 0, 
                      partner.company_revenue || 0
                    )}
                  </span>
                </td>
                <td className="numeric-cell">
                  <span className="client-count">{formatNumber(partner.active_clients || 0)}</span>
                </td>
                <td className="numeric-cell">
                  <span className="new-client-count">{formatNumber(partner.new_active_clients || 0)}</span>
                </td>
                <td className="numeric-cell">
                  <span className="total-volume">{formatVolume(partner.volume_usd || 0)}</span>
                </td>
                <td className="status-cell">
                  {partner.is_app_dev ? (
                    <span className="status-badge active">✅</span>
                  ) : (
                    <span className="status-badge inactive">❌</span>
                  )}
                </td>
                <td className="actions-cell">
                  <button 
                    className={`btn-sm btn-outline ${!showPII ? 'btn-locked' : ''}`}
                    onClick={() => {
                      if (showPII) {
                        onPartnerSelect(partner);
                      } else if (onRequestPIIAccess) {
                        onRequestPIIAccess(() => onPartnerSelect(partner));
                      }
                    }}
                    disabled={!showPII && !onRequestPIIAccess}
                    title={!showPII ? 'Enter password to unlock partner details' : 'View partner details'}
                  >
                    {!showPII ? (
                      <>
                        🔒 View Details
                      </>
                    ) : (
                      'View Details'
                    )}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PartnerTable; 