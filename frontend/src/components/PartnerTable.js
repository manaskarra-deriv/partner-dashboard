import React from 'react';
import Pagination from './Pagination';

const PartnerTable = ({ 
  partners, 
  loading, 
  onPartnerSelect,
  formatCurrency,
  formatNumber,
  getTierColor,
  sortField,
  sortDirection,
  onSortChange,
  // Pagination props
  currentPage,
  totalPages,
  totalCount,
  partnersPerPage,
  onPageChange,
  mainLoading = false
}) => {
  const getSortIcon = (field) => {
    if (sortField !== field) {
      return <span className="sort-icon sort-both">▲▼</span>;
    }
    return sortDirection === 'asc' ? 
      <span className="sort-icon sort-asc">▲</span> : 
      <span className="sort-icon sort-desc">▼</span>;
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
    <div className="table-wrapper">
      <div className="table-header">
        <h3 className="heading-md">Partners ({formatNumber(totalCount || partners.length)})</h3>
        
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
                Region
              </th>
              <th>
                Tier
              </th>
              <th onClick={() => onSortChange('total_earnings')} className="sortable">
                Total Earnings {getSortIcon('total_earnings')}
              </th>
              <th onClick={() => onSortChange('active_clients')} className="sortable">
                Active Clients {getSortIcon('active_clients')}
              </th>
              <th onClick={() => onSortChange('new_active_clients')} className="sortable">
                New Clients {getSortIcon('new_active_clients')}
              </th>
              <th>API Dev</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {partners.map((partner, index) => (
              <tr key={partner.partner_id || index} className="table-row">
                <td className="partner-id">
                  <span className="mono-text">{partner.partner_id}</span>
                </td>
                <td className="partner-name">
                  <div className="name-cell">
                    <strong>{partner.first_name} {partner.last_name}</strong>
                    <small className="text-secondary">@{partner.username}</small>
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
                  <strong>{formatCurrency(partner.total_earnings || 0)}</strong>
                  {partner.avg_past_3_months_earnings && (
                    <small className="text-secondary">
                      Avg: {formatCurrency(partner.avg_past_3_months_earnings)}
                    </small>
                  )}
                </td>
                <td className="numeric-cell">
                  <span className="client-count">{formatNumber(partner.active_clients || 0)}</span>
                </td>
                <td className="numeric-cell">
                  <span className="new-client-count">{formatNumber(partner.new_active_clients || 0)}</span>
                </td>
                <td className="status-cell">
                  {partner.is_app_dev ? (
                    <span className="status-badge active">✅ Yes</span>
                  ) : (
                    <span className="status-badge inactive">❌ No</span>
                  )}
                </td>
                <td className="actions-cell">
                  <button 
                    className="btn-sm btn-outline"
                    onClick={() => onPartnerSelect(partner)}
                  >
                    View Details
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