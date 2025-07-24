import React, { useState } from 'react';

const PartnerFilters = ({ filters, activeFilters, onFilterChange }) => {
  const [localFilters, setLocalFilters] = useState(activeFilters);

  const handleFilterChange = (key, value) => {
    const newFilters = {
      ...localFilters,
      [key]: value === '' ? undefined : value
    };
    
    // Remove undefined values
    Object.keys(newFilters).forEach(key => {
      if (newFilters[key] === undefined) {
        delete newFilters[key];
      }
    });
    
    setLocalFilters(newFilters);
    onFilterChange(newFilters);
  };

  const clearFilters = () => {
    setLocalFilters({});
    onFilterChange({});
  };

  const hasActiveFilters = Object.keys(localFilters).length > 0;

  return (
    <div className="filters-panel">
      <div className="filters-header">
        <h3 className="heading-sm">Filter Partners</h3>
        {hasActiveFilters && (
          <button 
            className="btn-sm btn-ghost" 
            onClick={clearFilters}
          >
            Clear All
          </button>
        )}
      </div>

      <div className="filters-grid">
        {/* Partner ID Search */}
        <div className="filter-group">
          <label className="filter-label">Partner ID</label>
          <input
            type="text"
            className="filter-select"
            placeholder="Enter Partner ID(s) - comma separated (e.g., 231489, 324325, 342356)..."
            value={localFilters.partner_id || ''}
            onChange={(e) => handleFilterChange('partner_id', e.target.value)}
          />
        </div>

        {/* Country Filter */}
        <div className="filter-group">
          <label className="filter-label">Country</label>
          <select
            className="filter-select"
            value={localFilters.country || ''}
            onChange={(e) => handleFilterChange('country', e.target.value)}
          >
            <option value="">All Countries</option>
            {filters.countries?.map(country => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>
        </div>

        {/* Region Filter */}
        <div className="filter-group">
          <label className="filter-label">Region</label>
          <select
            className="filter-select"
            value={localFilters.region || ''}
            onChange={(e) => handleFilterChange('region', e.target.value)}
          >
            <option value="">All Regions</option>
            {filters.regions?.map(region => (
              <option key={region} value={region}>
                {region}
              </option>
            ))}
          </select>
        </div>

        {/* Tier Filter */}
        <div className="filter-group">
          <label className="filter-label">Partner Tier</label>
          <select
            className="filter-select"
            value={localFilters.tier || ''}
            onChange={(e) => handleFilterChange('tier', e.target.value)}
          >
            <option value="">All Tiers</option>
            {filters.tiers?.map(tier => (
              <option key={tier} value={tier}>
                {tier}
              </option>
            ))}
          </select>
        </div>

        {/* API Developer Filter */}
        <div className="filter-group">
          <label className="filter-label">API Developer</label>
          <select
            className="filter-select"
            value={localFilters.is_app_dev || ''}
            onChange={(e) => handleFilterChange('is_app_dev', e.target.value)}
          >
            <option value="">All Partners</option>
            <option value="true">API Developers Only</option>
            <option value="false">Non-API Developers</option>
          </select>
        </div>
      </div>

      {/* Second row of filters */}
      <div className="filters-grid">
        {/* Active Clients Filter */}
        <div className="filter-group">
          <label className="filter-label">Active Clients</label>
          <div className="range-filter">
            <input
              type="number"
              className="filter-input-small"
              placeholder="Min"
              value={localFilters.active_clients_min || ''}
              onChange={(e) => handleFilterChange('active_clients_min', e.target.value)}
            />
            <span className="range-separator">to</span>
            <input
              type="number"
              className="filter-input-small"
              placeholder="Max"
              value={localFilters.active_clients_max || ''}
              onChange={(e) => handleFilterChange('active_clients_max', e.target.value)}
            />
          </div>
        </div>

        {/* New Clients Filter */}
        <div className="filter-group">
          <label className="filter-label">New Clients</label>
          <div className="range-filter">
            <input
              type="number"
              className="filter-input-small"
              placeholder="Min"
              value={localFilters.new_clients_min || ''}
              onChange={(e) => handleFilterChange('new_clients_min', e.target.value)}
            />
            <span className="range-separator">to</span>
            <input
              type="number"
              className="filter-input-small"
              placeholder="Max"
              value={localFilters.new_clients_max || ''}
              onChange={(e) => handleFilterChange('new_clients_max', e.target.value)}
            />
          </div>
        </div>

        {/* EtR Ratio Filter */}
        <div className="filter-group">
          <label className="filter-label">EtR Ratio</label>
          <select
            className="filter-select"
            value={localFilters.etr_filter || ''}
            onChange={(e) => handleFilterChange('etr_filter', e.target.value)}
          >
            <option value="">All Ratios</option>
            <option value="revenue-loss">Revenue Loss (--)</option>
            <option value="unprofitable">Unprofitable (-)</option>
            <option value="0-30">Fair (0-30%)</option>
            <option value="30-40">Excellent (30-40%)</option>
            <option value="40+">High (40%+)</option>
            <option value="custom">Custom Range</option>
          </select>
          {localFilters.etr_filter === 'custom' && (
            <div className="range-filter mt-2">
              <input
                type="number"
                className="filter-input-small"
                placeholder="Min %"
                value={localFilters.etr_min || ''}
                onChange={(e) => handleFilterChange('etr_min', e.target.value)}
              />
              <span className="range-separator">to</span>
              <input
                type="number"
                className="filter-input-small"
                placeholder="Max %"
                value={localFilters.etr_max || ''}
                onChange={(e) => handleFilterChange('etr_max', e.target.value)}
              />
            </div>
          )}
        </div>
      </div>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="active-filters">
          <div className="active-filters-header">
            <span className="text-sm text-secondary">Active Filters:</span>
          </div>
          <div className="filter-tags">
            {Object.entries(localFilters).map(([key, value]) => {
              if (!value || key === 'sort_by' || key === 'sort_order') return null;
              
              let displayName = key.replace('_', ' ');
              let displayValue = value;
              
              // Format display names
              if (key === 'partner_id') {
                displayName = 'Partner ID';
                displayValue = value;
              } else if (key === 'is_app_dev') {
                displayName = 'API Developer';
                displayValue = value === 'true' ? 'Yes' : 'No';
              } else if (key === 'active_clients_min') {
                displayName = 'Active Clients Min';
                displayValue = value;
              } else if (key === 'active_clients_max') {
                displayName = 'Active Clients Max';
                displayValue = value;
              } else if (key === 'new_clients_min') {
                displayName = 'New Clients Min';
                displayValue = value;
              } else if (key === 'new_clients_max') {
                displayName = 'New Clients Max';
                displayValue = value;
              } else if (key === 'etr_filter') {
                displayName = 'EtR Ratio';
                const etrLabels = {
                  'revenue-loss': 'Revenue Loss (--)',
                  'unprofitable': 'Unprofitable (-)',
                  '0-30': 'Fair (0-30%)',
                  '30-40': 'Excellent (30-40%)',
                  '40+': 'High (40%+)',
                  'custom': 'Custom Range'
                };
                displayValue = etrLabels[value] || value;
              } else if (key === 'etr_min') {
                displayName = 'EtR Min %';
                displayValue = value + '%';
              } else if (key === 'etr_max') {
                displayName = 'EtR Max %';
                displayValue = value + '%';
              }
              
              return (
                <div key={key} className="filter-tag">
                  <span className="filter-tag-label">{displayName}:</span>
                  <span className="filter-tag-value">{displayValue}</span>
                  <button
                    className="filter-tag-remove"
                    onClick={() => handleFilterChange(key, '')}
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default PartnerFilters; 